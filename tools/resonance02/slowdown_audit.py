"""POST-FREEZE supplementary slowdown diagnostics; never retunes frozen gates.

Usage: python -m tools.resonance02.slowdown_audit --output EVIDENCE_ROOT

Only existing checksum-pinned sources and rendered outputs are measured. This
module writes new SUPPLEMENTAL_AUDIT.json/.md files; no frozen file is edited.
All alignment assumptions and measurement definitions are exported with results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment
from scipy.signal import find_peaks, resample_poly
import soundfile as sf


N_FFT = 2048
HA = 512
REPO = Path(__file__).resolve().parents[2]
DEFINITIONS = {
    "status": "POST-FREEZE SUPPLEMENTARY DIAGNOSTIC; no gates retuned",
    "frame_reanalysis": "Periodic Hann N=2048; zero-padded centered frames. Input center i*512; output center i*round(512*ratio). Identical frequency bins in Hz.",
    "alignment_assumption": "The nominal stretch map is t_out=ratio*t_in. No delay, waveform-correlation or dynamic time alignment is fitted. Reanalysis errors therefore include local timing/remapping differences and fixed-window mixture changes.",
    "ipd_reliability": "Exclude DC/Nyquist. All four L/R input/output magnitudes must exceed max(1e-10, own channel/frame maximum*1e-4). Weight is fourth root of product of all four magnitudes. Report common-bin coverage of input reliable bins.",
    "ipd_error": "Weighted mean absolute principal angle of (phase_out_L-phase_out_R)-(phase_in_L-phase_in_R), in radians; also weighted RMS. This compares reanalyzed audio, not internal synthesis coefficients.",
    "channel_balance": "20*log10(RMS_L/RMS_R), full file; delta=output-input. Return null if either channel RMS is zero. Frame statistic is arithmetic mean absolute mapped-frame balance delta over frames where each channel RMS exceeds 1e-10.",
    "phase_prediction": "For each channel/bin use omega_hat[n-1]=omega+wrap(phi[n-1]-phi[n-2]-omega*H)/H. Error=wrap(phi[n]-phi[n-1]-H*omega_hat[n-1]). Three-frame magnitudes must each exceed max(1e-10, channel/frame maximum*1e-4); exclude DC/Nyquist; weight geometric mean magnitude. Report weighted cos(error) and absolute error. Input uses H=512; output uses H=round(512*ratio). Different hop lengths confound a direct score comparison.",
    "phase_prediction_scope": "A causal reliable-bin predictability proxy only. It does not identify partials, validate vertical harmonic coherence, estimate note identity, or establish perceptual quality.",
    "impulse_detection": "max(abs(channel)) trace; scipy find_peaks distance=round(0.10*sr), prominence=0.10*maximum trace. Known source nonzero samples must agree with manifest events. Expected output sample=round(source event sample*ratio). Minimum-total-absolute-distance one-to-one assignment; unmatched peaks are extra, unmatched source events missing.",
    "impulse_spread": "Within +/-50 ms of each expected event, duration between cumulative squared multichannel-summed energy quantiles 0.05 and 0.95. Also report fraction of output energy outside union of those neighborhoods.",
    "impulse_unchanged_screen": "Any extra/missing detected event or matched timing error>10 ms is flagged. This supplemental 48 kHz corpus result never overrides either preserved 16 kHz strict development failure.",
    "independent_tone_pitch": "Middle third; Hann-windowed FFT with nfft=8*segment length, log-magnitude quadratic interpolation around strongest positive-frequency bin. Report output/input and output/440 Hz cents.",
    "tone_reconstruction_artifact": "Unwindowed least-squares fit of sin/cos at independently estimated frequency plus DC on middle third. Residual RMS / signal RMS, fitted amplitude and DC. This reflects deviations from one sinusoid, not audible quality.",
    "peaks": "Read stored FLOAT WAVs as float64; sample peak and scipy resample_poly factor 4 peak estimate. No normalization, clipping or loudness matching; estimate is not certified true peak.",
    "decision_scope": "Descriptive post-freeze evidence only. No new threshold is used to promote a candidate. Frozen strict impulse failures and pending creator listening keep robust slowdown incomplete.",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wrap(value):
    return (value + np.pi) % (2 * np.pi) - np.pi


def centered_stft(x, centers):
    window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)
    padded = np.pad(x, ((N_FFT // 2, N_FFT // 2), (0, 0)))
    return np.asarray([
        np.fft.rfft(padded[int(center):int(center) + N_FFT] * window[:, None], axis=0)
        for center in centers
    ])


def reliable(magnitude):
    floor = np.maximum(1e-10, magnitude.max(axis=1, keepdims=True) * 1e-4)
    result = magnitude > floor
    result[:, [0, -1], :] = False
    return result


def phase_prediction(spectrum, hop):
    if len(spectrum) < 3:
        return {"weighted_cosine": None, "weighted_abs_error_rad": None, "reliable_bin_count": 0}
    magnitude, phase = np.abs(spectrum), np.angle(spectrum)
    omega = 2 * np.pi * np.arange(spectrum.shape[1])[None, :, None] / N_FFT
    previous = omega + wrap(phase[1:-1] - phase[:-2] - omega * hop) / hop
    error = wrap(phase[2:] - phase[1:-1] - hop * previous)
    mask = reliable(magnitude)
    valid = mask[2:] & mask[1:-1] & mask[:-2]
    weights = np.cbrt(magnitude[2:] * magnitude[1:-1] * magnitude[:-2]) * valid
    total = float(weights.sum())
    return {
        "weighted_cosine": float(np.sum(weights * np.cos(error)) / total) if total else None,
        "weighted_abs_error_rad": float(np.sum(weights * np.abs(error)) / total) if total else None,
        "reliable_bin_count": int(np.sum(valid)),
        "analysis_hop_samples": hop,
    }


def balance(x):
    levels = np.sqrt(np.mean(x * x, axis=0))
    return float(20 * np.log10(levels[0] / levels[1])) if np.all(levels > 0) else None


def stereo_reanalysis(x, y, ratio):
    hs = round(HA * ratio)
    count = min((len(x) - 1) // HA, (len(y) - 1) // hs) + 1
    centers_in, centers_out = np.arange(count) * HA, np.arange(count) * hs
    source = centered_stft(x, centers_in)
    output = centered_stft(y, centers_out)
    a, b = np.abs(source), np.abs(output)
    source_reliable, output_reliable = reliable(a), reliable(b)
    valid_source = np.all(source_reliable, axis=2)
    valid = valid_source & np.all(output_reliable, axis=2)
    phase_difference = wrap(np.angle(output[:, :, 0] * np.conj(output[:, :, 1]))
                            - np.angle(source[:, :, 0] * np.conj(source[:, :, 1])))
    weights = np.power(a[:, :, 0] * a[:, :, 1] * b[:, :, 0] * b[:, :, 1], 0.25) * valid
    total = float(weights.sum())
    input_balance, output_balance = balance(x), balance(y)
    frame_deltas = []
    padded_x = np.pad(x, ((N_FFT // 2, N_FFT // 2), (0, 0)))
    padded_y = np.pad(y, ((N_FFT // 2, N_FFT // 2), (0, 0)))
    for ci, co in zip(centers_in, centers_out):
        fx, fy = padded_x[ci:ci + N_FFT], padded_y[co:co + N_FFT]
        if np.all(np.sqrt(np.mean(fx * fx, axis=0)) > 1e-10) and np.all(np.sqrt(np.mean(fy * fy, axis=0)) > 1e-10):
            frame_deltas.append(abs(balance(fy) - balance(fx)))
    return {
        "frame_pairs": count,
        "ipd_weighted_mean_abs_error_rad": float(np.sum(weights * np.abs(phase_difference)) / total) if total else None,
        "ipd_weighted_rms_error_rad": float(np.sqrt(np.sum(weights * phase_difference ** 2) / total)) if total else None,
        "reliable_common_bin_count": int(valid.sum()),
        "input_reliable_bin_count": int(valid_source.sum()),
        "common_bin_coverage_of_input": float(valid.sum() / valid_source.sum()) if valid_source.sum() else None,
        "input_channel_balance_db": input_balance,
        "output_channel_balance_db": output_balance,
        "channel_balance_delta_db": output_balance - input_balance if input_balance is not None and output_balance is not None else None,
        "mapped_frame_mean_abs_channel_balance_delta_db": float(np.mean(frame_deltas)) if frame_deltas else None,
        "input_phase_prediction": phase_prediction(source, HA),
        "output_phase_prediction": phase_prediction(output, hs),
    }


def impulse_audit(x, y, sr, ratio, events_seconds):
    actual_source_events = np.flatnonzero(np.max(np.abs(x), axis=1) > 0)
    manifest_events = np.round(np.asarray(events_seconds) * sr).astype(int)
    if not np.array_equal(actual_source_events, manifest_events):
        raise ValueError("Impulse nonzero samples do not match frozen manifest event times")
    trace = np.max(np.abs(y), axis=1)
    detected, _ = find_peaks(trace, distance=round(0.10 * sr), prominence=0.10 * np.max(trace))
    expected = np.round(actual_source_events * ratio).astype(int)
    expected_assignment, observed_assignment = linear_sum_assignment(abs(expected[:, None] - detected[None, :]))
    pairs = []
    for ei, oi in zip(expected_assignment, observed_assignment):
        pairs.append({"expected_sample": int(expected[ei]), "observed_sample": int(detected[oi]),
                      "timing_error_ms": float((detected[oi] - expected[ei]) * 1000 / sr)})
    neighborhoods = np.zeros(len(y), dtype=bool)
    event_spreads = []
    for event in expected:
        lo, hi = max(0, event - round(0.05 * sr)), min(len(y), event + round(0.05 * sr) + 1)
        neighborhoods[lo:hi] = True
        energy = np.sum(y[lo:hi] ** 2, axis=1)
        if energy.sum():
            cumulative = np.cumsum(energy) / energy.sum()
            spread = float((np.searchsorted(cumulative, 0.95) - np.searchsorted(cumulative, 0.05)) * 1000 / sr)
        else:
            spread = None
        event_spreads.append({"expected_sample": int(event), "local_90pct_energy_spread_ms": spread,
                              "neighborhood_energy": float(energy.sum())})
    total_energy = float(np.sum(y * y))
    max_error = max((abs(pair["timing_error_ms"]) for pair in pairs), default=None)
    extra = [int(detected[i]) for i in range(len(detected)) if i not in set(observed_assignment)]
    missing = [int(expected[i]) for i in range(len(expected)) if i not in set(expected_assignment)]
    return {
        "source_event_samples": actual_source_events.tolist(),
        "expected_output_samples": expected.tolist(),
        "detected_output_samples": detected.tolist(),
        "expected_event_count": len(expected), "detected_event_count": len(detected),
        "extra_event_samples": extra, "missing_event_samples": missing,
        "assigned_events": pairs, "max_abs_timing_error_ms": max_error,
        "event_spreads": event_spreads,
        "energy_outside_50ms_neighborhoods_fraction": float(np.sum(y[~neighborhoods] ** 2) / total_energy) if total_energy else None,
        "unchanged_impulse_screen_failure": bool(extra or missing or max_error is None or max_error > 10.0),
        "scope": "Separate 48 kHz corpus fixture; original strict 16 kHz development failures remain failures",
    }


def tone_audit(x, sr):
    segment = x[len(x) // 3:2 * len(x) // 3, 0]
    spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment)), n=8 * len(segment)))
    peak = int(np.argmax(spectrum[1:]) + 1)
    logged = np.log(np.maximum(spectrum[peak - 1:peak + 2], 1e-30))
    offset = 0.5 * (logged[0] - logged[2]) / (logged[0] - 2 * logged[1] + logged[2])
    frequency = float((peak + offset) * sr / (8 * len(segment)))
    t = np.arange(len(segment)) / sr
    basis = np.column_stack((np.sin(2 * np.pi * frequency * t), np.cos(2 * np.pi * frequency * t), np.ones(len(t))))
    coefficients, _, _, _ = np.linalg.lstsq(basis, segment, rcond=None)
    residual = segment - basis @ coefficients
    return {"frequency_hz": frequency, "cents_from440": float(1200 * np.log2(frequency / 440)),
            "fitted_sine_amplitude": float(np.hypot(coefficients[0], coefficients[1])),
            "fitted_dc": float(coefficients[2]),
            "sine_fit_residual_rms_ratio": float(np.sqrt(np.mean(residual ** 2) / np.mean(segment ** 2)))}


def run(root):
    root = Path(root).resolve()
    freeze_path, manifest_path = root / "FREEZE.json", root / "SOURCE_MANIFEST.json"
    freeze, manifest = json.loads(freeze_path.read_text()), json.loads(manifest_path.read_text())
    assert sha(manifest_path) == freeze["source_manifest_sha256"]
    for path, digest in freeze["code_and_protocol"].items():
        assert sha(REPO / path) == digest, f"Frozen file changed: {path}"
    primary_path = root / "slowdown" / "metrics.json"
    primary = json.loads(primary_path.read_text())
    cache, records = {}, []
    for row in primary["records"]:
        name = row["source"]
        if name not in cache:
            cell = next(c for c in manifest["cells"] if c["name"] == name and c["sr"] == 48000 and c["channels"] == 2)
            source_path = root / cell["path"]
            assert sha(source_path) == cell["sha256"]
            x, sr = sf.read(source_path, dtype="float64", always_2d=True)
            assert sr == cell["sr"] and len(x) == cell["frames"]
            cache[name] = (cell, x, sr)
        cell, x, sr = cache[name]
        path = root / "slowdown" / row["path"]
        assert sha(path) == row["sha256"], f"Rendered output hash mismatch: {path}"
        y, output_sr = sf.read(path, dtype="float64", always_2d=True)
        assert sr == output_sr and y.shape[1] == 2 and np.all(np.isfinite(y))
        ratio = row["ratio"]
        output_4x = float(np.max(np.abs(resample_poly(y, 4, 1, axis=0))))
        record = {
            "source": name, "ratio": ratio, "path": row["path"], "sha256": sha(path),
            "source_path": cell["path"], "source_sha256": cell["sha256"],
            "input_samples": len(x), "output_samples": len(y),
            "target_samples": round(len(x) * ratio), "duration_error_samples": len(y) - round(len(x) * ratio),
            "sample_peak": float(np.max(np.abs(y))), "oversampled4x_peak_estimate": output_4x,
            "stereo_and_phase_reanalysis": stereo_reanalysis(x, y, ratio),
        }
        if name == "impulse":
            record["known_impulse_audit"] = impulse_audit(x, y, sr, ratio, cell["events_seconds"])
        if name == "simple_tone":
            source_tone, output_tone = tone_audit(x, sr), tone_audit(y, sr)
            record["independent_tone_audit"] = {"input": source_tone, "output": output_tone,
                "output_vs_input_cents": float(1200 * np.log2(output_tone["frequency_hz"] / source_tone["frequency_hz"]))}
        records.append(record)
        print("Audited", row["path"], flush=True)
    result = {"schema": 1, "status": DEFINITIONS["status"], "definitions": DEFINITIONS,
              "freeze_sha256": sha(freeze_path), "source_manifest_sha256": sha(manifest_path),
              "primary_metrics_sha256": sha(primary_path), "audit_script_sha256": sha(Path(__file__)),
              "frozen_files_verified": len(freeze["code_and_protocol"]), "outputs_verified": len(records),
              "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "soundfile": sf.__version__},
              "frozen_gate_status": primary["gate"], "records": records}
    destination = root / "slowdown" / "SUPPLEMENTAL_AUDIT.json"
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    write_report(root / "slowdown" / "SUPPLEMENTAL_AUDIT.md", result)
    return result


def write_report(path, result):
    lines = ["# Slowdown supplemental audit", "", "**POST-FREEZE supplementary diagnostic. No gates were retuned.**", "",
             f"Verified {result['outputs_verified']} rendered WAV hashes, their 5 source files, the frozen source manifest and {result['frozen_files_verified']} frozen code/protocol files.", "",
             "Measured output audio independently of synthesis coefficients. The nominal mapping is input frame center i*512 to output i*640 or i*768. No fitted time alignment was used. Local timing changes and different window mixtures contribute to the reported errors.", "",
             "## Recorded-piano stereo reanalysis", "",
             "|Source|Ratio|Path|Mean abs IPD error rad|Channel balance delta dB|", "|---|---|---|---|---|"]
    for row in result["records"]:
        if row["source"] in ("recorded_piano", "recorded_piano_reserved") and not any(row["path"].endswith("_" + m + ".wav") for m in ("velvet", "legato", "melt")):
            p = row["stereo_and_phase_reanalysis"]
            lines.append(f"|{row['source']}|{row['ratio']:.2f}|{row['path'].rsplit('_',1)[-1][:-4] if 'librosa' not in row['path'] else 'librosa independent'}|{p['ipd_weighted_mean_abs_error_rad']:.6f}|{p['channel_balance_delta_db']:+.6f}|")
    lines += ["", "These are post-freeze mapped-frame statistics. They cannot be promoted to a preregistered recorded-stereo acceptance test. The independent-channel librosa control has no transient treatment; it is not a proven transient-protecting comparator. The three synthetic fixtures have identical L/R signals, so their zero interchannel error is a narrow construction check.", "", "## Known impulse fixture", "", "|Ratio|Path|Detected/expected|Max timing error ms|Local 90% energy spreads ms|Extra peaks|", "|---|---|---|---|---|---|"]
    for row in result["records"]:
        if "known_impulse_audit" in row:
            p = row["known_impulse_audit"]
            label = "librosa" if "librosa" in row["path"] else ("protected" if "protected" in row["path"] else "raw")
            spreads = ", ".join(f"{e['local_90pct_energy_spread_ms']:.3f}" for e in p["event_spreads"])
            lines.append(f"|{row['ratio']:.2f}|{label}|{p['detected_event_count']}/{p['expected_event_count']}|{p['max_abs_timing_error_ms']:.3f}|{spreads}|{len(p['extra_event_samples'])}|")
    lines += ["", "This separate 48 kHz fixture does not replace the strict 16 kHz development tests. Those retained protected failures were 14.5 ms and 29 ms at ratios 1.25 and 1.50 respectively. Robust slowdown remains INCOMPLETE regardless of source-specific outcomes here.", "", "## Independent isolated-tone check", "", "|Ratio|Path|Pitch vs input cents|Sine-fit residual RMS ratio|Duration error samples|", "|---|---|---|---|---|"]
    for row in result["records"]:
        if "independent_tone_audit" in row:
            p = row["independent_tone_audit"]
            label = "librosa" if "librosa" in row["path"] else ("protected" if "protected" in row["path"] else "raw")
            lines.append(f"|{row['ratio']:.2f}|{label}|{p['output_vs_input_cents']:+.8f}|{p['output']['sine_fit_residual_rms_ratio']:.8f}|{row['duration_error_samples']}|")
    lines += ["", "## Harmonic-sustain phase-prediction proxy", "", "|Ratio|Path|Input weighted abs prediction error rad|Output weighted abs prediction error rad|Output weighted cosine|", "|---|---|---|---|---|"]
    for row in result["records"]:
        if row["source"] == "harmonic_sustain" and not any(row["path"].endswith("_" + m + ".wav") for m in ("velvet", "legato", "melt")):
            p = row["stereo_and_phase_reanalysis"]
            label = "librosa" if "librosa" in row["path"] else ("protected" if "protected" in row["path"] else "raw")
            lines.append(f"|{row['ratio']:.2f}|{label}|{p['input_phase_prediction']['weighted_abs_error_rad']:.6f}|{p['output_phase_prediction']['weighted_abs_error_rad']:.6f}|{p['output_phase_prediction']['weighted_cosine']:.6f}|")
    lines += ["", "This proxy measures reliable-bin temporal predictability. Input/output hop lengths differ; the scores do not establish a harmonic phase-coherence improvement or perceptual benefit. Synthesized exact harmonics are a narrow test, and no individual piano-string trajectory is identified.", "", "## Measurement definitions and limits", ""]
    for name, definition in DEFINITIONS.items():
        lines.append(f"- **{name}:** {definition}")
    lines += ["", "Full per-file results, reliable-bin counts/coverage, phase-prediction proxies, channel balances, sample/4x peaks, waveform hashes and event matches are in SUPPLEMENTAL_AUDIT.json. No listening preference, musical improvement or robust-piano acceptance is inferred.", ""]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.output)
