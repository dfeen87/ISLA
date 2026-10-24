"""Rebuild the README's classical Remastered listening examples, without devices.

Run from the repository root: python -m tools.classical_showcase
Requires the base project, FFmpeg and research-only pyloudnorm==0.2.0.
The bundled, hash-pinned source recordings are never rewritten.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import tempfile

import numpy as np
import pyloudnorm as pyln
import scipy
import soundfile as sf

from isla.remastered import CORE_SHA256, RenderRequest, render_preview, signal_metrics

ROOT = Path(__file__).resolve().parents[1]
RATE = 44100
PASSAGE_SECONDS = 18
MODES = ("bypass", "velvet", "legato", "melt")
WORKS = (
    dict(
        folder="mozart-remastered", filename="lacrimosa-piano.ogg", start=12,
        sha256="64da4163217f10fce0aee705c7a48f1e21c195f7cc52730bf5bde7fadcd4e382",
        title="Mozart, Requiem in D minor, 'Lacrimosa' – piano arrangement",
        performer="Lệ Xuân", arrangement="Sigismund Thalberg, Op. 70, No. 5A",
        license="CC BY-SA 4.0", license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        page="https://commons.wikimedia.org/wiki/File:Mozart,_Requiem_in_D_minor,_%27Lacrimosa%27_%E2%80%93_piano_arrangement.ogg",
        revision="https://commons.wikimedia.org/w/index.php?oldid=551942809",
        download="https://upload.wikimedia.org/wikipedia/commons/b/b0/Mozart%2C_Requiem_in_D_minor%2C_%27Lacrimosa%27_%E2%80%93_piano_arrangement.ogg",
        codec="Vorbis",
    ),
    dict(
        folder="saint-saens-remastered", filename="maestoso-brass-organ.mp3", start=0,
        sha256="c5f09c9ffe52762e6b556d79612ba1e07a3dacd57295e4146a09525807b755ba",
        title="Saint-Saëns, Symphony No. 3 in C minor, Op. 78, 'Organ' – Maestoso finale",
        performer="Stellar Brass, United States Air Force Academy Band",
        arrangement="Gary Poffenbarger, brass and organ",
        license="Public domain in the United States; U.S. Air Force official work",
        license_url="https://creativecommons.org/publicdomain/mark/1.0/",
        page="https://commons.wikimedia.org/wiki/File:Symphony_No._3_in_C_Minor_-_II._Maestoso_-_Stellar_Brass_-_United_States_Air_Force_Academy_Band.mp3",
        revision="https://commons.wikimedia.org/w/index.php?oldid=1044296594",
        download="https://upload.wikimedia.org/wikipedia/commons/d/da/Symphony_No._3_in_C_Minor_-_II._Maestoso_-_Stellar_Brass_-_United_States_Air_Force_Academy_Band.mp3",
        codec="MP3",
    ),
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fade(x):
    """Shared 25 ms boundary fades, before any research processing."""
    x = x.copy()
    length = round(.025 * RATE)
    ramp = np.linspace(0., 1., length, dtype=np.float32)[:, None]
    x[:length] *= ramp
    x[-length:] *= ramp[::-1]
    return x


def prepare_inputs(work, source):
    if sha256(source) != work["sha256"]:
        raise ValueError("Bundled source hash mismatch; refusing to render.")
    decoded, rate = sf.read(source, dtype="float32", always_2d=True)
    if rate != RATE or decoded.shape[1] != 2:
        raise ValueError("Expected the pinned 44.1 kHz stereo recording.")
    start, length = work["start"] * RATE, PASSAGE_SECONDS * RATE
    passage = np.ascontiguousarray(decoded[start:start + length])
    if len(passage) != length or not np.isfinite(passage).all():
        raise ValueError("Source passage is incomplete or nonfinite.")
    # Pitch-preserving slowdown precedes the model: these are new renders on
    # slower input, rather than playback-speed changes to already wet files.
    slow_frames = PASSAGE_SECONDS * RATE * 5 // 3
    with tempfile.TemporaryDirectory(prefix="isla-classical-") as directory:
        input_path = Path(directory) / "passage.wav"
        output_path = Path(directory) / "slow.wav"
        sf.write(input_path, passage, RATE, subtype="FLOAT")
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(input_path),
            "-af", f"atempo=0.6,apad,atrim=end_sample={slow_frames}",
            "-c:a", "pcm_f32le", str(output_path),
        ], check=True)
        slow, slow_rate = sf.read(output_path, dtype="float32", always_2d=True)
    if slow_rate != RATE or slow.shape != (slow_frames, 2):
        raise ValueError("Slowdown did not produce exactly 30 seconds of stereo.")
    common_gain = min(1., .5 / max(float(np.max(abs(passage))),
                                  float(np.max(abs(slow)))))
    inputs = {
        "100pct": fade((passage * common_gain).astype(np.float32)),
        "060pct": fade((slow * common_gain).astype(np.float32)),
    }
    return decoded, inputs, common_gain


def render_work(work):
    output = ROOT / "docs/audio" / work["folder"]
    source = output / "source" / work["filename"]
    decoded, inputs, input_gain = prepare_inputs(work, source)
    meter = pyln.Meter(RATE)
    raw = []
    for speed, x in inputs.items():
        source_bytes = x.tobytes()
        for mode in MODES:
            diagnostic = None
            if mode == "bypass":
                y = x.copy()
            else:
                y, diagnostic = render_preview(x, RATE, RenderRequest(mode, 100))
                if not diagnostic["numerical_pass"]:
                    raise ValueError(f"Research screens failed: {speed}/{mode}")
                if diagnostic["raw_output"]["exact_copy"]:
                    raise ValueError(f"No processing was exercised: {speed}/{mode}")
            if x.tobytes() != source_bytes:
                raise ValueError("Renderer changed its source buffer.")
            # Use the same float64 meter path before and after PCM encoding.
            # The renderer itself retains its original float32 calculations.
            y = np.asarray(y, dtype=np.float64)
            loudness = float(meter.integrated_loudness(y))
            if not np.isfinite(loudness):
                raise ValueError("Cannot loudness-match a silent/nonfinite example.")
            raw.append((speed, mode, y, loudness, diagnostic))
            print(f"Rendered {work['folder']}/{speed}/{mode}", flush=True)

    # One integrated target across all eight examples. Scalar attenuation only:
    # no compressor, limiter, EQ, reverb or production-DSP changes.
    target = min(-23., min(row[3] for row in raw) - 3.)
    predicted_peak = max(
        signal_metrics(y)["four_x_peak_estimate"] * 10 ** ((target - loudness) / 20)
        for _, _, y, loudness, _ in raw
    )
    if predicted_peak > .8:
        target += 20 * np.log10(.8 / predicted_peak)
    records = []
    for speed, mode, y, loudness, diagnostic in raw:
        gain = 10 ** ((target - loudness) / 20)
        path = output / f"{speed}-{mode}.flac"
        # Integrated gating can move a boundary block after PCM quantization.
        # Recheck the actual file and correct only its constant scalar gain.
        for adjustment in range(5):
            if not 0 < gain <= 1:
                raise ValueError("Listening-copy gain must only attenuate.")
            sf.write(path, y * gain, RATE, subtype="PCM_24")
            saved, rate = sf.read(path, always_2d=True)
            matched = float(meter.integrated_loudness(saved))
            if abs(matched - target) <= .01:
                break
            gain *= 10 ** ((target - matched) / 20)
        measurements = signal_metrics(saved)
        if (rate != RATE or saved.shape != y.shape or not np.isfinite(saved).all()
                or abs(matched - target) > .01
                or max(measurements.values()) >= .98):
            raise ValueError(f"Saved listening-copy verification failed: {path}")
        records.append(dict(
            path=str(path.relative_to(output)), sha256=sha256(path),
            speed_ratio=1. if speed == "100pct" else .6, mode=mode,
            frames=len(saved), seconds=len(saved) / RATE,
            raw_lufs=loudness, listening_gain_db=float(20 * np.log10(gain)),
            pcm_gain_adjustments=adjustment,
            matched_lufs=matched, **measurements, research_report=diagnostic,
        ))

    # Reject accidental duplicated model files, in addition to the raw-copy gate.
    if len({record["sha256"] for record in records}) != 8:
        raise ValueError("Expected eight distinct example files.")
    report = dict(
        schema=1, purpose="README listening showcase; not scientific listening acceptance",
        renderer="isla.remastered.render_preview / Experiment 02 governed, 100% depth",
        scientific_verdict="REVISE / INCONCLUSIVE; no audible-improvement claim",
        research_core_sha256=CORE_SHA256,
        renderer_sha256=sha256(ROOT / "isla/remastered.py"),
        script_sha256=sha256(Path(__file__)),
        code_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        source=dict(
            path=str(source.relative_to(output)),
            **{key: work[key] for key in ("sha256", "title", "performer", "arrangement",
                                         "license", "license_url", "page", "revision", "download")},
            source_frames=len(decoded), sample_rate=RATE, channels=2,
            passage_start_seconds=work["start"], passage_end_seconds=work["start"] + PASSAGE_SECONDS,
        ),
        preparation=dict(
            slowdown="FFmpeg atempo=0.6,apad,atrim=end_sample=1323000; pitch preserved; before DSP",
            boundary_fades_ms=25, common_input_gain=input_gain,
            output=f"24-bit PCM FLAC; no further lossy encoding (source is already {work['codec']})",
            matching="pyloudnorm default BS.1770 K weighting and integrated gating; scalar attenuation only",
            target_lufs=float(target),
            peak_note="4x resample_poly peak estimate is a probe, not a certified true-peak meter",
        ),
        environment=dict(
            python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
            soundfile=sf.__version__, libsndfile=sf.__libsndfile_version__,
            pyloudnorm=importlib.metadata.version("pyloudnorm"),
            ffmpeg=subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
        ),
        verified=True, records=records,
    )
    (output / "PROVENANCE.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"Verified eight FLACs at {target:.2f} LUFS; research equations unchanged.")


def main():
    for work in WORKS:
        render_work(work)


if __name__ == "__main__":
    main()
