"""Reproduce the isolated experiment; no device, download, or routing access.

PYTHONPATH=.:<pyloudnorm directory> python -m tools.identity_lab.run --output <new folder>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dsp_study import metrics, rms, envelope, f0_acf
from dsp_study_fixtures import fixtures, fixture_manifest
from tools.identity_lab.dsp import SWEEPS, SHOWCASE, render

BASELINE = "6a732e03c3f0adc3f555e0ecb002e365b7e3385f"
SHOW_SOURCES = ("solo_piano", "connected_melody", "harmonic_sustain", "percussion",
                "dense_mix", "stereo_probe", "gapped_tone", "near_silence", "silence")


def array_hash(x):
    return hashlib.sha256(np.asarray(x, dtype="<f4").tobytes()).hexdigest()


def file_hash(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sources(rate, channels):
    audio = fixtures(rate, channels)
    audio["near_silence"] = (audio["simple_tone"] * np.float32(1e-7)).astype(np.float32)
    x = audio["simple_tone"].copy()
    # Exact 300 ms gap with fixed 10 ms cosine edges, shared before all modes.
    start, stop, edge = round(2.1 * rate), round(2.4 * rate), round(.01 * rate)
    fade = (.5 + .5 * np.cos(np.pi * np.arange(edge) / (edge - 1)))[:, None]
    x[start-edge:start] *= fade
    x[start:stop] = 0
    x[stop:stop+edge] *= fade[::-1]
    audio["gapped_tone"] = x
    return audio


def db_ratio(a, b):
    return float(20 * np.log10(a / b)) if a and b else None


def attack_metrics(y, original, rate, events):
    a, b = envelope(y, rate), envelope(original, rate)
    shifts, levels = [], []
    for event in events:
        start = round(event["time_seconds"] * rate)
        stop = min(len(y), start + round(.06 * rate))
        if stop <= start + 1:
            continue
        da, db = np.diff(a[start:stop]), np.diff(b[start:stop])
        if db.max(initial=0) < 1e-12:
            continue
        shifts.append(float((np.argmax(da) - np.argmax(db)) * 1000 / rate))
        d = db_ratio(rms(y[start:start+round(.01*rate)]), rms(original[start:start+round(.01*rate)]))
        if d is not None:
            levels.append(d)
    return dict(attack_max_abs_shift_ms=max(map(abs, shifts), default=0.),
                attack_max_abs_10ms_gain_db=max(map(abs, levels), default=0.),
                attack_shifts_ms=shifts, attack_10ms_gain_db=levels)


def pair_metrics(y, original, rate, raw, events):
    result = metrics(y, original, rate, raw)
    gain = rms(original) / rms(y) if rms(y) else 1.
    ea, eb = envelope(y * gain, rate), envelope(original, rate)
    result["envelope_roughness_ratio"] = rms(np.diff(ea)) / rms(np.diff(eb)) if rms(np.diff(eb)) else None
    result.update(attack_metrics(y, original, rate, events))
    if y.shape[1] == 2 and min(rms(y[:, 0]), rms(y[:, 1]), rms(original[:, 0]), rms(original[:, 1])):
        result["balance_delta_db"] = db_ratio(rms(y[:, 0]), rms(y[:, 1])) - db_ratio(rms(original[:, 0]), rms(original[:, 1]))
    else:
        result["balance_delta_db"] = None
    return result


def screen(record):
    m = record["versus_original"]
    failures = []
    for key, limit in [("rms_gain_db", 1.), ("attack_max_abs_shift_ms", 1.),
                       ("attack_max_abs_10ms_gain_db", 1.),
                       ("stereo_correlation_delta", .02), ("balance_delta_db", .25)]:
        if m.get(key) is not None and abs(m[key]) > limit:
            failures.append(key)
    if m["raw_samples_over_fullscale"] or m["raw_peak"] >= 1:
        failures.append("raw_fullscale")
    if record.get("pitch_delta_cents") is not None and abs(record["pitch_delta_cents"]) >= 1:
        failures.append("pitch")
    if record.get("gap_center_peak", 0) != 0:
        failures.append("gap")
    if record["profile"] == "legato" and record["fixture"] == "connected_melody" and m["envelope_roughness_ratio"] > 1.05:
        failures.append("continuity_proxy")
    return failures


def save_listening(root, name, versions, rate):
    """Same 6 s passage; no cropping or extra fades; scalar-only level edits."""
    meter = pyln.Meter(rate)
    loudness = {label: float(meter.integrated_loudness(x)) for label, x in versions.items()}
    # Do not boost sub-gate material or digital silence to normal listening level.
    normal = all(np.isfinite(value) for value in loudness.values())
    target = min(-23., loudness["bypass"] - 3.) if normal else None
    gains = {label: 10 ** ((target - loudness[label]) / 20) if normal else 1.
             for label in versions}
    predicted = max(float(np.max(abs(resample_poly(x * gains[label], 4, 1, axis=0))))
                    for label, x in versions.items())
    common = min(1., .80 / predicted) if predicted else 1.
    if target is not None:
        target += 20 * np.log10(common)
    result = []
    for label, x in versions.items():
        directory = root / "listening" / name
        directory.mkdir(parents=True, exist_ok=True)
        gain = gains[label] * common
        y = x.astype(float) * gain
        # FLOAT WAV retains near-silence below a PCM24 quantization step.
        path = directory / (label + (".wav" if not normal else ".flac"))
        sf.write(path, y, rate, subtype="FLOAT" if not normal else "PCM_24")
        saved, _ = sf.read(path, always_2d=True)
        after = float(meter.integrated_loudness(saved))
        error = float(np.max(abs(saved - y)))
        if normal:
            assert abs(after - target) < .01
            assert error <= 2 ** -23
        peak = float(np.max(abs(saved)))
        probe = float(np.max(abs(resample_poly(saved, 4, 1, axis=0))))
        assert max(peak, probe) < 1
        result.append(dict(fixture=name, version=label, rate=rate, channels=2,
            frames=len(x), gain_db=float(20*np.log10(gain)), target_lufs=target,
            raw_lufs=loudness[label] if normal else None, saved_lufs=after if np.isfinite(after) else None,
            sample_peak=peak, oversampled_4x_peak_probe=probe, quantization_max_error=error,
            raw_float32_le_sha256=array_hash(x), path=str(path.relative_to(root)), sha256=file_hash(path)))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    records, baselines, source_records, listening = [], [], [], []
    for rate in (44100, 48000):
        for channels in (1, 2):
            manifest = fixture_manifest(rate, channels)
            (root / f"source_manifest_{rate}_{channels}.json").write_text(json.dumps(manifest, indent=2)+"\n")
            for name, x in sources(rate, channels).items():
                source_records.append(dict(fixture=name, rate=rate, channels=channels,
                    float32_le_sha256=array_hash(x), frames=len(x), peak=float(np.max(abs(x)))))
                originals = {}
                versions = {}
                for mode in ("bypass", *SWEEPS):
                    y, raw = render(x, rate, mode)
                    originals[mode] = y
                    if mode == "bypass":
                        np.testing.assert_array_equal(y, x)
                    baselines.append(dict(fixture=name, rate=rate, channels=channels, mode=mode,
                        float32_le_sha256=array_hash(y), versus_bypass=metrics(y, x, rate, raw)))
                    versions["bypass" if mode == "bypass" else mode+"_original"] = y
                events = (manifest["fixtures"].get(name, {}).get("events", [])
                          if name in ("solo_piano", "percussion", "connected_melody") else [])
                for profile, amounts in SWEEPS.items():
                    for amount in amounts:
                        y, raw = render(x, rate, profile, {profile: amount})
                        assert np.isfinite(raw).all()
                        pair = pair_metrics(y, originals[profile], rate, raw, events)
                        record = dict(fixture=name, rate=rate, channels=channels, profile=profile,
                            amount=amount, float32_le_sha256=array_hash(y),
                            versus_original=pair, versus_bypass=metrics(y, x, rate, raw))
                        if name == "simple_tone":
                            record["pitch_delta_cents"] = float(1200*np.log2(f0_acf(y, rate)/f0_acf(originals[profile], rate)))
                        if name == "gapped_tone":
                            region = y[round(2.1*rate)+2048:round(2.4*rate)-2048]
                            record["gap_center_peak"] = float(np.max(abs(region)))
                        record["screen_failures"] = screen(record)
                        records.append(record)
                        if amount == SHOWCASE[profile]:
                            versions[profile+"_experiment"] = y
                if rate == 48000 and channels == 2 and name in SHOW_SOURCES:
                    rawroot = root / "raw_float" / name
                    rawroot.mkdir(parents=True)
                    for label, y in versions.items():
                        sf.write(rawroot / (label+".wav"), y, rate, subtype="FLOAT")
                    sf.write(rawroot / "source.wav", x, rate, subtype="FLOAT")
                    listening.extend(save_listening(root, name, versions, rate))
            print(f"Measured {rate} Hz / {channels} channels", flush=True)
    payload = dict(baseline_commit=BASELINE, platform=platform.platform(), python=platform.python_version(),
        dependencies={p: importlib.metadata.version(p) for p in ("numpy", "scipy", "soundfile", "pyloudnorm")},
        sweeps=SWEEPS, showcase=SHOWCASE, source_records=source_records,
        baselines=baselines, candidates=records)
    (root / "measurements.json").write_text(json.dumps(payload, indent=2, allow_nan=False)+"\n")
    columns = ["fixture", "rate", "channels", "profile", "amount", "rms_gain_db", "matched_relative_rms", "raw_peak",
               "attack_max_abs_shift_ms", "attack_max_abs_10ms_gain_db", "stereo_correlation_delta", "balance_delta_db", "envelope_roughness_ratio", "screen_failures"]
    with (root / "comparison.csv").open("w") as f:
        writer = csv.DictWriter(f, columns)
        writer.writeheader()
        for item in records:
            flat = dict(item, **item["versus_original"])
            writer.writerow({k: flat[k] for k in columns})
    provenance = dict(source="Deterministic mathematical synthesis; no external recordings or samples",
        licensing="Repository MIT license applies to generator and generated research outputs; no third-party audio rights required",
        baseline_commit=BASELINE, rate=48000, channels=2, seconds=6,
        edits="1536-sample alignment; full six-second source; no crop or presentation fades; one stereo-linked scalar per file; no limiting",
        extensions={"near_silence":"simple_tone multiplied by float32(1e-7), fixed gain, FLOAT WAV",
                    "gapped_tone":"simple_tone with exact zero 2.1–2.4 s and fixed 10 ms cosine edges"},
        meter="pyloudnorm 0.2.0 BS.1770 default, 400 ms gated integration; below-gate files retain unity gain",
        target="minimum of -23 LUFS and Bypass minus 3 LU; common attenuation if 4x peak probe exceeds .80",
        peak_note="4x scipy resample_poly probe is not a certified true-peak measurement",
        files=listening)
    (root / "listening_provenance.json").write_text(json.dumps(provenance, indent=2, allow_nan=False)+"\n")
    hashes = {str(p.relative_to(root)): file_hash(p) for p in sorted(root.rglob("*")) if p.is_file()}
    (root / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2)+"\n")
    print(f"Complete: {len(baselines)} baseline and {len(records)} candidate records; {len(listening)} listening files", flush=True)


if __name__ == "__main__":
    main()
