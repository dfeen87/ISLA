"""Build compact baseline or numerical-robustness listening references.

Requires an existing controlled-study tree containing music/audio/raw/ and
recordings/. This never rerenders DSP, opens audio hardware, or captures audio.
Pins the original source and raw baseline bytes so robustness experiments
cannot silently replace the baseline reference. The listening-only crop,
common fades, silence, loudness gains and PCM24 quantization are documented.

python tools/dsp_showcase.py --input ../../outputs/study \
    --output docs/audio/live-baseline

python tools/dsp_showcase.py --input ../../outputs/study \
    --current ../../outputs/implementation/music \
    --output docs/audio/live-robustness

Research dependencies: numpy, scipy, soundfile>=0.14, pyloudnorm==0.2.0.
Different regenerated baseline WAV bytes are intentionally rejected; use the
verified study renders rather than relabeling a new implementation baseline.
The optional current renders must match the implementation's before_after
audio manifest and its exact on-disk processing-source SHA-256 fingerprints.
Use --render-missing explicitly to reconstruct only absent original-baseline
raw WAVs with the frozen research engine. Acquire the original WAV separately
first. Existing bytes are verified and never overwritten by that option.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import struct

import numpy as np
import pyloudnorm as pyln
import scipy
from scipy.signal import resample_poly
import soundfile as sf


BASELINE_COMMIT = "4eb2412682f8b3c6321ce5c8887314850ac9a697"
SOURCE_SHA256 = "9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15"
RAW_SHA256 = {
    "bypass": "a8aea2cd3acf60e25d8a557dac9449061162a2729c04f699a9e5183c80102120",
    "velvet": "bccdae7fd5535775215caeddaf7727c9a8e7eb4ca37dbcd2f68901b50f2e5ea4",
    "legato": "c7edeea903ba14ebfb2fc25732d0524f51e6eb610a8c33f026792ec6999dc9fd",
    "melt": "6c827940d50be9b743cc4d7d9e278c324d1b3c0f15e91f18f918c9d9beac6b9c",
}
MODES = tuple(RAW_SHA256)
STRENGTHS = {"bypass": None, "velvet": 0.35, "legato": 0.55, "melt": 0.75}
RATE = 48000
START_SECONDS, END_SECONDS = 2.0, 8.0
FADE_SECONDS = 0.005
GUARD_SECONDS = 0.125
FROZEN_DSP_SHA256 = "7adc9ee6121d4bf6ca49d78a2589169d560385b3de9a95840284d6d17b774b4e"
HISTORICAL_PEAK_TIMESTAMP = {"bypass": 1792819058, "velvet": 1792819058,
                             "legato": 1792819058, "melt": 1792819059}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def peak_probe(audio: np.ndarray) -> float:
    """An oversampled diagnostic, not a certified true-peak meter."""
    return float(np.max(np.abs(resample_poly(audio, 4, 1, axis=0))))


def archived_wave_header(payload: bytes, mode: str) -> bytes:
    """Restore only historical PEAK timestamp metadata for exact file hashes.

    libsndfile embeds wall-clock creation time in FLOAT WAV PEAK chunks even
    when sample data are identical. Reconstructing the archived byte stream
    requires its original metadata value, not a claim about this run's date.
    The complete pinned hash subsequently verifies header and all sample data.
    """
    require(payload[:4] == b"RIFF" and payload[8:12] == b"WAVE", "Unexpected WAV container")
    data = bytearray(payload)
    offset = 12
    found = False
    while offset + 8 <= len(data):
        size = struct.unpack_from("<I", data, offset + 4)[0]
        require(offset + 8 + size <= len(data), "Invalid WAV chunk length")
        if data[offset:offset + 4] == b"PEAK":
            require(not found and size >= 8, "Unexpected WAV PEAK metadata")
            struct.pack_into("<I", data, offset + 12, HISTORICAL_PEAK_TIMESTAMP[mode])
            found = True
        offset += 8 + size + size % 2
    require(found, "FLOAT WAV lacks expected PEAK timestamp metadata")
    return bytes(data)


def render_missing_baseline(study: Path) -> list[str]:
    """Opt-in four-mode baseline reconstruction, with no audio acquisition."""
    repo = Path(__file__).resolve().parents[1]
    original = study / "recordings" / "Emotional_piano.wav"
    require(original.exists(), "Original WAV missing; run dsp_study_acquire.py separately first")
    require(sha256(original) == SOURCE_SHA256, "Original source checksum mismatch")
    archive = repo / "docs" / "research" / "live-dsp-study" / "study"
    for relative in ("recordings/RECORDING_PROVENANCE.json", "music/measurements.json"):
        destination = study / relative
        if not destination.exists():
            payload = (archive / relative).read_bytes()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(payload)
    measurements = json.loads((study / "music" / "measurements.json").read_text())
    require(measurements["baseline_commit"] == BASELINE_COMMIT, "Wrong archived baseline metadata")
    raw_dir = study / "music" / "audio" / "raw"
    missing = []
    for mode in MODES:
        path = raw_dir / f"emotional_piano_00s_{mode}.wav"
        if path.exists():
            require(sha256(path) == RAW_SHA256[mode], f"{mode}: existing baseline WAV differs; refusing overwrite")
        else:
            missing.append(mode)
    if not missing:
        return []
    require(sha256(repo / "tools" / "dsp_study_baseline.py") == FROZEN_DSP_SHA256,
            "Frozen baseline DSP reference changed")
    for name in ("isla/harmonics.py", "phased_music_notes/harmonics.py"):
        require(sha256(repo / name) == measurements["production_source_sha256"][name],
                f"Shared original harmonic kernel changed: {name}")
    # This source helper does channel conversion/resampling only. DSP must be
    # explicitly the frozen class, never dsp_study.py's current StreamingDSP.
    from dsp_study import recording_sources
    from dsp_study_baseline import StreamingDSP as FrozenDSP
    sources, _ = recording_sources([original], RATE, 2)
    source = sources["emotional_piano_00s"]
    expected_input = next(r["sha256"] for r in measurements["fixtures"]
                          if r["fixture"] == "emotional_piano_00s"
                          and r["rate"] == RATE and r["channels"] == 2)
    require(hashlib.sha256(source.tobytes()).hexdigest() == expected_input,
            "Converted source differs from archived baseline input")
    raw_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for mode in missing:
        dsp = FrozenDSP(RATE, 2)
        dsp.select(mode)
        count = ((len(source) + dsp.delay + dsp.hop - 1) // dsp.hop) * dsp.hop
        padded = np.pad(source, ((0, count - len(source)), (0, 0)))
        emitted = np.concatenate([dsp.process_block(block) for block in padded.reshape(-1, dsp.hop, 2)])
        aligned = emitted[dsp.delay:dsp.delay + len(source)]
        buffer = io.BytesIO()
        sf.write(buffer, aligned, RATE, format="WAV", subtype="FLOAT")
        payload = archived_wave_header(buffer.getvalue(), mode)
        actual = hashlib.sha256(payload).hexdigest()
        require(actual == RAW_SHA256[mode],
                f"{mode}: regenerated baseline checksum {actual} differs; library-dependent bytes are not accepted")
        path = raw_dir / f"emotional_piano_00s_{mode}.wav"
        with path.open("xb") as handle:
            handle.write(payload)
        created.append(path.name)
    return created


def implementation_inputs(current: Path, baseline_conversion: dict) -> dict:
    """Verify numerical-fix identity independently of an uncommitted Git HEAD."""
    report_path = current.parent / "before_after.json"
    report = json.loads(report_path.read_text())
    require(report["kind"] == "LIVE numerical robustness before-after", "Wrong implementation report kind")
    require(report["baseline_commit"] == BASELINE_COMMIT, "Wrong numerical-fix baseline")
    require(report["input_hashes_verified"] is True, "Implementation source inputs were not verified")
    require(report["musical_tuning_changed"] is False and report["artistic_strengths"] == [0.35, 0.55, 0.75], "Unexpected musical retuning")
    repo = Path(__file__).resolve().parents[1]
    source_hashes = {name: report["source_sha256"][name] for name in ("isla/streaming.py", "isla/spectral.py")}
    for name, expected in source_hashes.items():
        require(sha256(repo / name) == expected, f"Numerical-fix processing source changed: {name}")
    conversion = next(r for r in report["recording_transformations"]
                      if r.get("fixture") == "emotional_piano_00s"
                      and r.get("target_rate") == RATE and r.get("channels") == 2)
    require(conversion == baseline_conversion, "Baseline/current source transformation differs")
    audio_hashes = {row["path"]: row["sha256"] for row in report["audio_files"]}
    raw_hashes = {}
    for mode in MODES:
        key = f"{current.name}/audio/raw/emotional_piano_00s_{mode}.wav"
        require(key in audio_hashes, f"Implementation audio manifest lacks {key}")
        raw_hashes[mode] = audio_hashes[key]
    return {"report": report, "report_sha256": sha256(report_path),
            "source_hashes": source_hashes, "raw_hashes": raw_hashes}


def build(study: Path, output: Path, current: Path | None = None) -> dict:
    measurement_path = study / "music" / "measurements.json"
    provenance_path = study / "recordings" / "RECORDING_PROVENANCE.json"
    measurements = json.loads(measurement_path.read_text())
    provenance = json.loads(provenance_path.read_text())
    require(measurements["baseline_commit"] == BASELINE_COMMIT, "Wrong study baseline commit")
    source = next(s for s in provenance["sources"] if s["filename"] == "Emotional_piano.wav")
    require(source["sha256"] == SOURCE_SHA256, "Wrong original source checksum in provenance")
    require(source["license_spdx"] == "CC0-1.0" and source["author"] == "triangelx", "Unexpected original attribution/license")
    original = study / "recordings" / source["filename"]
    require(sha256(original) == SOURCE_SHA256, "Original source bytes do not match the verified CC0 source")
    original_info = sf.info(original)
    require((original_info.samplerate, original_info.channels, original_info.frames, original_info.subtype)
            == (44100, 2, 705600, "PCM_16"), "Unexpected original source format")
    conversion = next(r for r in measurements["source_metadata"]
                      if r.get("fixture") == "emotional_piano_00s"
                      and r.get("target_rate") == RATE and r.get("channels") == 2)
    require(conversion["original_sha256"] == SOURCE_SHA256, "Study source conversion checksum mismatch")
    require(conversion["guard_frames"] == round(GUARD_SECONDS * RATE), "Unexpected study silence guards")
    implementation = implementation_inputs(current, conversion) if current is not None else None
    raw_root = (current if current is not None else study / "music") / "audio" / "raw"
    raw_hashes = implementation["raw_hashes"] if implementation else RAW_SHA256
    input_guard = conversion["guard_frames"]
    start = input_guard + round(START_SECONDS * RATE)
    stop = input_guard + round(END_SECONDS * RATE)
    guard = round(GUARD_SECONDS * RATE)
    fade_frames = round(FADE_SECONDS * RATE)
    ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(fade_frames) / (fade_frames - 1))
    prepared = {}
    meter = pyln.Meter(RATE)
    before = {}
    for mode in MODES:
        raw_path = raw_root / f"emotional_piano_00s_{mode}.wav"
        require(sha256(raw_path) == raw_hashes[mode], f"{mode}: raw render WAV checksum mismatch")
        info = sf.info(raw_path)
        audio, rate = sf.read(raw_path, dtype="float64", always_2d=True)
        require((rate, info.channels, info.subtype, len(audio)) == (RATE, 2, "FLOAT", 588000), f"{mode}: unexpected raw format")
        require(bool(np.isfinite(audio).all()), f"{mode}: nonfinite raw samples")
        if implementation and mode == "bypass":
            baseline_path = study / "music" / "audio" / "raw" / raw_path.name
            require(sha256(baseline_path) == RAW_SHA256[mode], "Original Bypass reference checksum mismatch")
            baseline_audio, _ = sf.read(baseline_path, dtype="float64", always_2d=True)
            require(np.array_equal(audio, baseline_audio), "Numerical-fix Bypass differs from original baseline samples")
        # The raw study has already removed the DSP's 1536-frame delay. Its
        # 6000-frame source guard is separate and must be included in this crop.
        excerpt = audio[start:stop].copy()
        excerpt[:fade_frames] *= ramp[:, None]
        excerpt[-fade_frames:] *= ramp[::-1, None]
        excerpt = np.pad(excerpt, ((guard, guard), (0, 0)))
        prepared[mode] = excerpt
        before[mode] = float(meter.integrated_loudness(excerpt))
        require(np.isfinite(before[mode]), f"{mode}: invalid excerpt loudness")

    target = min(-23.0, before["bypass"] - 3.0)
    predicted_peak = max(peak_probe(prepared[m]) * 10 ** ((target - before[m]) / 20) for m in MODES)
    if predicted_peak > 0.85:
        target += 20 * np.log10(0.85 / predicted_peak)
    if implementation:
        require(abs(target - (-23.0)) < 1e-12, "Current comparison does not share the baseline -23 LUFS target")
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for mode in MODES:
        gain = 10 ** ((target - before[mode]) / 20)
        unquantized = prepared[mode] * gain
        path = output / f"{mode}.flac"
        sf.write(path, unquantized, RATE, format="FLAC", subtype="PCM_24", compression_level=1.0)
        saved, rate = sf.read(path, dtype="float64", always_2d=True)
        info = sf.info(path)
        after = float(meter.integrated_loudness(saved))
        error = float(np.max(np.abs(saved - unquantized)))
        sample_peak = float(np.max(np.abs(saved)))
        oversampled_peak = peak_probe(saved)
        require((info.samplerate, info.channels, info.subtype, info.frames) == (RATE, 2, "PCM_24", 300000), f"{mode}: invalid saved format")
        require(abs(after - target) <= 0.01, f"{mode}: PCM24 loudness match exceeds 0.01 LU")
        require(error <= 2 ** -23 + 1e-12, f"{mode}: unexpected PCM24 quantization error")
        require(max(sample_peak, oversampled_peak) < 1.0, f"{mode}: output headroom failure")
        require(not np.any(saved[:guard]) and not np.any(saved[-guard:]), f"{mode}: presentation guards changed")
        records.append({
            "mode": mode, "baseline_strength": STRENGTHS[mode],
            "input_raw_filename": f"music/audio/raw/emotional_piano_00s_{mode}.wav",
            "input_raw_sha256": raw_hashes[mode], "file": path.name,
            "sha256": sha256(path), "size_bytes": path.stat().st_size,
            "format": info.format, "subtype": info.subtype,
            "samplerate": RATE, "channels": info.channels,
            "frames": info.frames, "duration_seconds": info.duration,
            "faded_excerpt_integrated_lufs_before_gain": before[mode],
            "target_integrated_lufs": float(target),
            "saved_integrated_lufs_after_quantization": after,
            "lufs_target_error": after - target,
            "constant_stereo_linked_gain": float(gain),
            "constant_gain_db": float(20 * np.log10(gain)),
            "sample_peak": sample_peak, "oversampled_4x_peak_probe": oversampled_peak,
            "max_pcm24_quantization_error": error,
        })
    result = {
        "schema_version": 1, "purpose": "README listening reference from original LIVE baseline, before robustness fixes",
        "baseline_commit": BASELINE_COMMIT,
        "production_source_sha256": measurements.get("production_source_sha256", {}),
        "original_source": {k: source[k] for k in (
            "title", "filename", "author", "author_url", "work_date", "license", "license_spdx", "license_url",
            "commons_page_url", "commons_revision_url", "upstream_source_url", "original_download_url", "sha256", "sha1")},
        "original_format": {"format": "WAV", "subtype": "PCM_16", "samplerate": 44100,
                            "channels": 2, "frames": 705600, "duration_seconds": 16.0},
        "instrument_provenance": "Source title describes piano music; inspected pages do not establish physical, sampled or synthesized instrumentation.",
        "prior_input_conversion": conversion,
        "prior_live_render": "Fresh original-baseline StreamingDSP per mode; identical guarded source; all banks continuously warm; 1536-frame output delay removed by the study harness.",
        "selected_original_source_seconds": [START_SECONDS, END_SECONDS],
        "selected_raw_file_frame_range_end_exclusive": [start, stop],
        "listening_only_edits": {
            "common_edge_fade": "5 ms raised cosine, first/last source samples zero, applied equally to both channels and all modes",
            "edge_fade_frames": fade_frames, "added_silence_each_end_frames": guard,
            "added_silence_each_end_seconds": GUARD_SECONDS,
            "gain": "One constant gain per mode, identical for L/R, shared integrated-loudness target; no limiter or dynamic normalization",
            "quantization": "Float render to signed 24-bit PCM; FLAC stores the resulting PCM losslessly. Raw float renders are retained separately as measurement references.",
        },
        "loudness_meter": "pyloudnorm default BS.1770 K weighting, 400 ms absolute/relative gated integrated loudness",
        "shared_target_rule": "At or below -23 LUFS and 3 LU below faded Bypass; common further reduction if 4x peak prediction requires it",
        "peak_probe_limit": "4x scipy resample_poly peak probe, not a certified true-peak measurement",
        "pcm24_lsb": 2 ** -23,
        "perceptual_acceptance": "No new owner listening, blind discrimination result, musical tuning, or audible improvement is claimed.",
        "audio_hardware_used": False,
        "reproduce": "PYTHONPATH=. python tools/dsp_showcase.py --input study_out/study --render-missing --output docs/audio/live-baseline",
        "input_verification": "Original WAV and all four raw study WAV hashes must match the pinned original-baseline bytes; regenerated library-dependent differences are rejected.",
        "optional_missing_baseline_reconstruction": {
            "flag": "--render-missing (explicit opt-in only)",
            "reference": "tools/dsp_study_baseline.py", "reference_sha256": FROZEN_DSP_SHA256,
            "scope": "Four Emotional Piano modes at 48 kHz stereo only; missing raw files and historical JSON only; no overwrite or acquisition",
            "wav_peak_timestamp_metadata_restored": HISTORICAL_PEAK_TIMESTAMP,
            "header_note": "Restores the original archive's WAV PEAK timestamps for complete file-hash reproducibility; sample bytes remain unmodified and every completed file hash is verified before exclusive creation.",
        },
        "dependencies": {"numpy": np.__version__, "scipy": scipy.__version__, "soundfile": sf.__version__,
                         "libsndfile": sf.__libsndfile_version__, "pyloudnorm": importlib.metadata.version("pyloudnorm")},
        "records": records, "total_audio_bytes": sum(r["size_bytes"] for r in records),
    }
    if implementation:
        result.update({
            "purpose": "Numerical-robustness fix listening comparison under review; no artistic tuning or audible-quality claim",
            "processing_kind": "numerical-robustness",
            "processing_description": implementation["report"]["processing"],
            "production_source_sha256": implementation["source_hashes"],
            "implementation_before_after_sha256": implementation["report_sha256"],
            "implementation_audio_hash_metadata": {
                key: implementation["report"][key] for key in
                ("audio_hashes_recorded_after_render",) if key in implementation["report"]
            },
            "processing_identity_note": "Source SHA-256 pins identify the numerical implementation; baseline_commit identifies the unchanged historical reference, not a commit containing the fix.",
            "review_status": "Numerical fix under review. No artistic retuning, perceptual success, native monitoring or acoustic acceptance is claimed.",
            "prior_live_render": "Equivalent source and fresh numerical-fix StreamingDSP per mode; source transformations match original baseline; all banks continuously warm; 1536-frame delay removed by implementation harness.",
            "reproduce": "PYTHONPATH=. python tools/dsp_showcase.py --input study_out/study --render-missing --current <implementation/music> --output docs/audio/live-robustness",
            "input_verification": "Original WAV checksum pinned; current raw WAV SHA-256 checked against implementation before_after.json audio_files; isla/streaming.py and isla/spectral.py checked against its processing-source hashes; full Bypass samples equal pinned original baseline.",
            "baseline_comparison": "../live-baseline/PROVENANCE.json",
        })
    (output / "PROVENANCE.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    write_markdown(output, result)
    return result


def write_markdown(output: Path, data: dict) -> None:
    source = data["original_source"]
    current = data.get("processing_kind") == "numerical-robustness"
    lines = [
        "# Numerical-robustness fix listening comparison" if current else "# Original LIVE baseline listening samples", "",
        (f"These four files represent the **numerical fix under review**, compared with original baseline [`{BASELINE_COMMIT[:12]}`](https://github.com/dfeen87/ISLA/commit/{BASELINE_COMMIT}). The fix adds virtual silent WOLA prehistory and bounds spectral correction by float32 uncertainty. Velvet, Legato and Melt retain strengths **0.35 / 0.55 / 0.75**. No artistic retuning, audible improvement, owner preference or native acceptance is claimed. Processing identity is pinned by source hashes, rather than an uncommitted Git SHA."
         if current else f"These four files are original-baseline references from [`{BASELINE_COMMIT[:12]}`](https://github.com/dfeen87/ISLA/commit/{BASELINE_COMMIT}), before the separate robustness fixes. Velvet, Legato and Melt retain strengths **0.35 / 0.55 / 0.75**. No musical tuning, improved-sound claim or new owner listening acceptance is associated with these assets."), "",
        f"Source: **Emotional Piano** by **triangelx**, May 23, 2013, published under [CC0 1.0]({source['license_url']}). The [Commons page]({source['commons_page_url']}) attributes the [Freesound original]({source['upstream_source_url']}), which also states CC0. [Pinned Commons revision]({source['commons_revision_url']}) · [Original WAV]({source['original_download_url']}). Instrument and recording methods are unverified; physical acoustic piano is not assumed.", "",
        "The original is **16 seconds, 44,100 Hz, stereo WAV / signed PCM16**. Its SHA-256 is:", "",
        f"`{source['sha256']}`", "",
        "## Render and listening edits", "",
        ("The implementation comparison used the same original seconds 0–12, SciPy `resample_poly` conversion to 48 kHz (default Kaiser 5.0), and 6000 zero frames per end as the original study. Each mode was rendered from equivalent numerical-fix state and the shared 1536-frame DSP delay removed. The complete Bypass waveform equals the pinned original-baseline Bypass. This script reuses existing raw float WAVs and never runs DSP or opens audio hardware."
         if current else "The controlled study first selected original seconds 0–12, converted to 48 kHz using SciPy `resample_poly` (default Kaiser 5.0), added 6000 zero frames per end, and rendered each mode from equivalent original-baseline state. It removed the shared 1536-frame DSP delay. These assets reuse those existing raw float WAVs; this script never runs the current DSP or opens audio hardware."), "",
        "All four samples select **original seconds 2–8**, corresponding to raw-file frames **102000:390000**. Common **5 ms raised-cosine edge fades** and **0.125 seconds of silence at each end** are presentation edits. They do not constitute changes to LIVE. The musical excerpt is 6 seconds; each delivered file lasts **6.25 seconds**.", "",
        "Integrated loudness is recomputed after the crop/fades. Each mode receives one constant stereo-linked gain toward the same target, at or below −23 LUFS and 3 LU below Bypass, with extra common reduction if needed for headroom. There is no limiter or dynamic normalization. PCM24 FLAC quantization is measured separately; FLAC is lossless for its stored PCM24, rather than bit-identical to the raw float DSP render.", "",
        "| File | Gain (dB) | Shared target (LUFS) | Saved LUFS | Sample peak | 4× peak probe | Bytes |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in data["records"]:
        lines.append(f"| [{r['mode'].title()}]({r['file']}) | {r['constant_gain_db']:.4f} | {r['target_integrated_lufs']:.4f} | {r['saved_integrated_lufs_after_quantization']:.4f} | {r['sample_peak']:.6f} | {r['oversampled_4x_peak_probe']:.6f} | {r['size_bytes']:,} |")
    maximum_lu = max(abs(r["lufs_target_error"]) for r in data["records"])
    maximum_quant = max(r["max_pcm24_quantization_error"] for r in data["records"])
    lines += ["", f"All outputs are **48 kHz stereo FLAC / PCM24**, 300,000 frames. Maximum remeasured target error: **{maximum_lu:.3g} LU**, below 0.01 LU. Maximum measured quantization error: **{maximum_quant:.3g} full scale**, bounded by one PCM24 step ({2**-23:.3g}). The 4× oversampled peak is a probe, not a certified true-peak measurement. Total audio size: **{data['total_audio_bytes']:,} bytes**.", "",
              "## Reproduce and verify", "", "From a fresh repository checkout, with NumPy, SciPy, SoundFile >=0.14 and `pyloudnorm==0.2.0` installed:", "", "```sh",
              "python tools/dsp_study_acquire.py --output study_out/study/recordings", data["reproduce"], "```", "",
              ("The baseline `--input` is the controlled-study `study/` directory. Generate the numerical-fix comparison artifacts using the implementation report's reproduction workflow first; then replace `<implementation/music>` with its `music/` directory, containing `audio/raw/` and with `before_after.json` in its parent directory. `--render-missing` reconstructs old baseline references only, not the numerical-fix renders. The report's audio-file hashes, source transformations and exact `isla/streaming.py` / `isla/spectral.py` SHA-256 values are verified before encoding. The showcase command does not download, monitor or capture."
               if current else "The input is the existing controlled-study `study/` directory containing `music/audio/raw/`, `music/measurements.json`, the original `recordings/Emotional_piano.wav` and its provenance JSON. Exact original/raw checksums are enforced; different regenerated bytes are intentionally rejected. No downloads, monitoring or capture occur in this command."), "",
              "The separate acquisition command downloads only the reviewed CC0 originals. `--render-missing` explicitly reconstructs only absent Emotional Piano baseline raw WAVs, using frozen `tools/dsp_study_baseline.py`, equivalent fresh state and the original delay/flush convention. It copies missing historical measurement/provenance JSON from the checked-in study archive; it does not run the full 224-render study or use the current production DSP. Existing files are verified and never overwritten. Omit this flag to require an already populated input tree.", "",
              "Exact WAV reconstruction also restores the archived PEAK-chunk timestamp metadata (1792819058; Melt1792819059). SoundFile otherwise inserts the current creation time, changing a whole-file checksum despite identical samples. Only that historical header field is normalized; complete pinned SHA-256 checks verify every header/sample byte before a missing WAV is written. This is archival byte reconstruction, not a claim that a new run happened at the historical timestamp. Cross-library differences are rejected rather than mislabeled as the original reference.", "",
              "The [machine-readable provenance](PROVENANCE.json) records all source/raw/output SHA-256 checksums, conversion metadata, gains, quantization errors, sample/oversampled peaks and dependency versions. The [controlled study](../../research/live-dsp-study/README.md) retains raw-vs-matched measurement distinctions and outstanding native/perceptual gates. Keep playback volume fixed while comparing; equal integrated LUFS does not establish equal momentary or perceived loudness.", ""]
    if current:
        lines += ["## Compare with the original baseline", "",
                  "The baseline assets remain the README showcase. These eight files use the same source crop, fades, guards, format and −23 LUFS target. Compare each mode with its corresponding baseline; no listening verdict has been supplied.", "",
                  "| Mode | Original baseline | Numerical fix under review |", "|---|---|---|"]
        lines.extend(f"| {mode.title()} | [Baseline](../live-baseline/{mode}.flac) | [Numerical fix]({mode}.flac) |" for mode in MODES)
        lines += ["", "Exact processing-source identities from the implementation report:", "",
                  "| Source | SHA-256 |", "|---|---|"]
        lines.extend(f"| `{name}` | `{value}` |" for name, value in data["production_source_sha256"].items())
        lines += ["", f"Implementation `before_after.json` SHA-256: `{data['implementation_before_after_sha256']}`.", ""]
    (output / "PROVENANCE.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="existing original controlled-study root")
    parser.add_argument("--output", type=Path, required=True, help="destination for four FLACs and provenance")
    parser.add_argument("--current", type=Path, help="optional implementation/music directory with parent before_after.json")
    parser.add_argument("--render-missing", action="store_true", help="explicitly reconstruct absent raw baseline references with frozen DSP; never downloads or overwrites")
    args = parser.parse_args()
    if args.render_missing:
        created = render_missing_baseline(args.input)
        print(f"Reconstructed {len(created)} absent frozen-baseline raw WAVs")
    result = build(args.input, args.output, args.current)
    label = "numerical-fix" if args.current else "original-baseline"
    print(f"Verified four {label} FLACs, {result['total_audio_bytes']:,} audio bytes")


if __name__ == "__main__":
    main()
