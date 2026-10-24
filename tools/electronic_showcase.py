"""Render the README's traditional/Remastered electronic comparisons offline.

python -m tools.electronic_showcase
Requires base project dependencies and research-only pyloudnorm==0.2.0.
No audio devices, application changes, network access, or DSP retuning.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import io
import itertools
import json
from pathlib import Path
import platform
import subprocess

import numpy as np
import pyloudnorm as pyln
import scipy
import soundfile as sf

from isla.remastered import CORE_SHA256, RenderRequest, output_metrics, render_preview, signal_metrics
from isla.remastered_streaming import RemasteredStreamingDSP
from isla.streaming import StreamingDSP

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audio/electronic-comparison"
RATE, CHANNELS, SECONDS, CONTEXT_SECONDS = 44100, 2, 24, 2
MODES = ("velvet", "legato", "melt")
STRENGTHS = {"velvet": .35, "legato": .55, "melt": .75}
SOURCES = (
    dict(slug="outbreaker", title="Outbreaker", artist="Hinkik", start=48,
         parts=("outbreaker.mp3.part1", "outbreaker.mp3.part2"),
         sha256="1049fbeeaf7919bec6d50219f525681aa4b75a0f8827a4ce13059623cbcde4ab",
         page="https://www.newgrounds.com/audio/listen/681530",
         artist_page="https://hinkik.newgrounds.com/",
         download="https://audio-download.ngfiles.com/681000/681530_Outbreaker.mp3?f1461524830"),
    dict(slug="ember", title="Ember", artist="Kubbi", start=40,
         sha256="85dc877c4e303c0455c50b7d5da99cd95ff57e436c61a78ddb49f3aa07d17e88",
         page="https://www.newgrounds.com/audio/listen/974737",
         artist_page="https://kubbi.newgrounds.com/",
         download="https://audio-download.ngfiles.com/974000/974737_Ember.mp3?f1603642917"),
)
PROCESSING_FILES = (
    "isla/streaming.py", "isla/spectral.py", "isla/harmonics.py",
    "phased_music_notes/harmonics.py", "isla/remastered_streaming.py",
    "isla/remastered.py", "tools/resonance02/core.py",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source):
    folder = OUTPUT / source["slug"] / "source"
    paths = [folder / name for name in source.get("parts", (source["slug"] + ".mp3",))]
    # Concatenating the source parts restores the original MP3 exactly; the
    # upload-size packaging has no audio conversion or metadata changes.
    payload = b"".join(path.read_bytes() for path in paths)
    if hashlib.sha256(payload).hexdigest() != source["sha256"]:
        raise ValueError("Source hash mismatch; refusing to render.")
    decoded, rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
    if rate != RATE or decoded.shape[1] != CHANNELS or not np.isfinite(decoded).all():
        raise ValueError("Expected a finite 44.1 kHz stereo recording.")
    begin = (source["start"] - CONTEXT_SECONDS) * RATE
    frames = (SECONDS + CONTEXT_SECONDS) * RATE
    segment = decoded[begin:begin + frames].copy()
    if segment.shape != (frames, CHANNELS):
        raise ValueError("Source does not cover the selected passage and context.")
    # Decode overshoots are measured, never clipped. One shared attenuation
    # supplies headroom before either engine; output matching is separate.
    gain = min(1., .4 / float(np.max(np.abs(segment))))
    segment = (segment * gain).astype(np.float32)
    return segment, dict(
        **source, license="CC BY-SA 3.0",
        license_url="https://creativecommons.org/licenses/by-sa/3.0/",
        license_checked_date="2026-10-24",
        source_parts=[dict(path=str(path.relative_to(OUTPUT)), sha256=sha256(path),
                           bytes=path.stat().st_size) for path in paths],
        bytes=len(payload),
        decoded_frames=len(decoded), decoded_source=signal_metrics(decoded),
        input_gain_db=float(20 * np.log10(gain)),
        prepared_pcm_sha256=hashlib.sha256(segment.tobytes()).hexdigest(),
        prepared_input=signal_metrics(segment),
    )


def stream_render(x, engine, mode):
    dsp = (StreamingDSP(RATE, CHANNELS) if engine == "traditional"
           else RemasteredStreamingDSP(RATE, CHANNELS, intensity=100))
    dsp.select(mode)
    count = ((len(x) + dsp.delay + dsp.hop - 1) // dsp.hop) * dsp.hop
    padded = np.pad(x, ((0, count - len(x)), (0, 0)))
    blocks = []
    for block in padded.reshape(-1, dsp.hop, CHANNELS):
        blocks.append(dsp.process_block(block))
    aligned = np.concatenate(blocks)[dsp.delay:dsp.delay + len(x)]
    if aligned.shape != x.shape or not np.isfinite(aligned).all():
        raise ValueError("Stream flush/alignment failed.")
    if mode == "bypass" and aligned.tobytes() != x.tobytes():
        raise ValueError("Time-aligned streaming Bypass differs from prepared input.")
    return aligned


def presentation(raw):
    # All seven versions get the same crop and edge fade after processing.
    x = raw[CONTEXT_SECONDS * RATE:].astype(np.float64)
    fade_frames = round(.025 * RATE)
    ramp = np.linspace(0., 1., fade_frames)[:, None]
    x[:fade_frames] *= ramp
    x[-fade_frames:] *= ramp[::-1]
    return x


def render_source(source):
    x, metadata = prepare(source)
    before = x.tobytes()
    dry = stream_render(x, "traditional", "bypass")
    if not np.array_equal(dry, stream_render(x, "remastered", "bypass")):
        raise ValueError("The two engines do not share exact aligned Bypass.")
    raw = {"original": dry}
    evidence = {"original": dict(engine="shared time-aligned input", mode="bypass")}
    for engine, mode in itertools.product(("traditional", "remastered"), MODES):
        key = engine + "-" + mode
        y = stream_render(x, engine, mode)
        evidence[key] = dict(
            engine=engine, mode=mode,
            traditional_strength=STRENGTHS[mode] if engine == "traditional" else None,
            remastered_depth_percent=100 if engine == "remastered" else None,
            raw_full_context=output_metrics(x, y),
        )
        if engine == "remastered":
            reference, report = render_preview(x, RATE, RenderRequest(mode, 100))
            error = float(np.max(np.abs(y - reference.astype(np.float32))))
            if error > 1e-7 or not report["numerical_pass"]:
                raise ValueError("Remastered output differs from its frozen offline authority.")
            evidence[key].update(offline_equivalence_max_error=error, research_report=report)
        if not evidence[key]["raw_full_context"]["peak_screen_pass"]:
            raise ValueError("Raw output failed peak screen; no clipping or limiting applied.")
        raw[key] = y
        print(f"Rendered {source['slug']}/{key}", flush=True)
    if x.tobytes() != before:
        raise ValueError("Processing changed the prepared input.")

    prepared = {key: presentation(y) for key, y in raw.items()}
    meter = pyln.Meter(RATE)
    levels = {key: float(meter.integrated_loudness(y)) for key, y in prepared.items()}
    if not all(np.isfinite(level) for level in levels.values()):
        raise ValueError("Cannot match silent/nonfinite examples.")
    target = min(-23., min(levels.values()) - 3.)
    predicted_peak = max(signal_metrics(y)["four_x_peak_estimate"] *
                         10 ** ((target - levels[key]) / 20)
                         for key, y in prepared.items())
    if predicted_peak > .8:
        target += 20 * np.log10(.8 / predicted_peak)

    records, saved_audio = [], {}
    folder = OUTPUT / source["slug"]
    for key, y in prepared.items():
        gain = 10 ** ((target - levels[key]) / 20)
        path = folder / (key + ".flac")
        # Correct only scalar attenuation if PCM rounding changes a gated block.
        for adjustment in range(5):
            if not 0 < gain <= 1:
                raise ValueError("Listening-copy gain must only attenuate.")
            sf.write(path, y * gain, RATE, subtype="PCM_24")
            saved, rate = sf.read(path, always_2d=True)
            matched = float(meter.integrated_loudness(saved))
            if abs(matched - target) <= .01:
                break
            gain *= 10 ** ((target - matched) / 20)
        metrics = signal_metrics(saved)
        if (saved.shape != (SECONDS * RATE, CHANNELS) or rate != RATE
                or not np.isfinite(saved).all() or abs(matched - target) > .01
                or max(metrics.values()) >= .98):
            raise ValueError("Saved FLAC verification failed: " + str(path))
        reference = prepared["original"]
        residual = output_metrics(reference, y)
        records.append(dict(
            path=str(path.relative_to(OUTPUT)), sha256=sha256(path), bytes=path.stat().st_size,
            frames=len(saved), sample_rate=rate, channels=CHANNELS, seconds=SECONDS,
            raw_presentation_lufs=levels[key], matched_lufs=matched,
            listening_gain_db=float(20 * np.log10(gain)), pcm_gain_adjustments=adjustment,
            **metrics, presentation_residual_to_original=residual, evidence=evidence[key],
        ))
        saved_audio[key] = saved
    separations = []
    for a, b in itertools.combinations(saved_audio, 2):
        metrics = output_metrics(saved_audio[a], saved_audio[b])
        if metrics["exact_copy"]:
            raise ValueError("Two decoded comparison outputs are identical.")
        separations.append(dict(a=a, b=b, **metrics))
    return dict(source=metadata, target_lufs=float(target), records=records,
                saved_pairwise_separations=separations)


def main():
    hashes = {path: sha256(ROOT / path) for path in PROCESSING_FILES}
    if hashes["tools/resonance02/core.py"] != CORE_SHA256:
        raise ValueError("Frozen research core changed.")
    report = dict(
        schema=1, purpose="Current traditional/Remastered LIVE worker comparison, rendered offline",
        code_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        processing_source_sha256=hashes, renderer_script_sha256=sha256(Path(__file__)),
        environment=dict(python=platform.python_version(), numpy=np.__version__,
                         scipy=scipy.__version__, soundfile=sf.__version__,
                         libsndfile=sf.__libsndfile_version__,
                         pyloudnorm=importlib.metadata.version("pyloudnorm")),
        method=dict(sample_rate=RATE, channels=CHANNELS, seconds=SECONDS,
                    context_seconds=CONTEXT_SECONDS, dsp_delay_removed_frames=1536,
                    speed_ratio=1., boundary_fade_ms=25, output="24-bit PCM FLAC",
                    matching="One integrated LUFS target per song, scalar attenuation only",
                    peak_note="4x polyphase estimate is a probe, not a certified true-peak meter"),
        research_verdict="REVISE / INCONCLUSIVE; numerical separation does not establish preference",
        songs=[render_source(source) for source in SOURCES],
    )
    if hashes != {path: sha256(ROOT / path) for path in PROCESSING_FILES}:
        raise ValueError("Processing source changed during rendering.")
    report["verified"] = True
    (OUTPUT / "PROVENANCE.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print("Verified 14 matched FLACs; both Bypass engines exact; 6 frozen-equation checks passed.")


if __name__ == "__main__":
    main()
