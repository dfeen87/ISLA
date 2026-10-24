"""Supplement the generated corpus with one checksum-pinned CC0 recording.

Supply an already acquired Emotional_piano.wav; this script never downloads.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from tools.identity_lab.dsp import SWEEPS, SHOWCASE, render
from tools.identity_lab.run import (BASELINE, file_hash, array_hash, metrics,
                                    pair_metrics, save_listening, screen)

EXPECTED = "9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    assert file_hash(args.source) == EXPECTED
    source, native = sf.read(args.source, always_2d=True)
    assert native == 44100 and source.shape == (705600, 2)
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.source, args.output / "Emotional_piano.wav")
    baselines, records, listening, sources = [], [], [], []
    for rate in (44100, 48000):
        for channels in (1, 2):
            x = source[2*native:8*native]
            if rate != native:
                x = resample_poly(x, 160, 147, axis=0)
            if channels == 1:
                x = x.mean(axis=1, keepdims=True)
            x = np.pad(x, ((round(.125*rate), round(.125*rate)), (0, 0))).astype(np.float32)
            name = "recorded_piano"
            sources.append(dict(fixture=name, rate=rate, channels=channels, frames=len(x), float32_le_sha256=array_hash(x)))
            original, versions = {}, {}
            for mode in ("bypass", *SWEEPS):
                y, raw = render(x, rate, mode)
                original[mode] = y
                versions["bypass" if mode == "bypass" else mode+"_original"] = y
                baselines.append(dict(fixture=name, rate=rate, channels=channels, mode=mode,
                    float32_le_sha256=array_hash(y), versus_bypass=metrics(y, x, rate, raw)))
            np.testing.assert_array_equal(original["bypass"], x)
            for profile, amounts in SWEEPS.items():
                for amount in amounts:
                    y, raw = render(x, rate, profile, {profile: amount})
                    pair = pair_metrics(y, original[profile], rate, raw, [])
                    pair["attack_max_abs_shift_ms"] = max(map(abs, pair["onset_offsets_ms"]), default=0.)
                    # No excitation annotations for the recording. The generated
                    # corpus tests first-10-ms attack gain independently.
                    pair["attack_max_abs_10ms_gain_db"] = None
                    r = dict(fixture=name, rate=rate, channels=channels, profile=profile, amount=amount,
                        float32_le_sha256=array_hash(y), versus_original=pair,
                        versus_bypass=metrics(y, x, rate, raw))
                    r["screen_failures"] = screen(r)
                    records.append(r)
                    if amount == SHOWCASE[profile]:
                        versions[profile+"_experiment"] = y
            if rate == 48000 and channels == 2:
                rawroot = args.output / "raw_float" / name
                rawroot.mkdir(parents=True)
                for label, y in dict(versions, source=x).items():
                    sf.write(rawroot / (label+".wav"), y, rate, subtype="FLOAT")
                listening = save_listening(args.output, name, versions, rate)
            print(f"Measured recording {rate}/{channels}", flush=True)
    provenance = dict(title="Emotional Piano", author="triangelx", publication="2013-05-23",
        original_source="https://freesound.org/people/triangelx/sounds/189175/",
        mirror="https://commons.wikimedia.org/wiki/File:Emotional_piano.wav",
        license="CC0 1.0", license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        license_verified="2026-10-24 on original Freesound page; pinned Commons revision unavailable via web tool",
        source_sha256=EXPECTED, original_format="16 s, 44100 Hz, stereo PCM16 WAV",
        origin="Reused original from prior local research; SHA verified before reading; no prior evidence overwritten",
        edits="Original seconds 2–8; scipy resample_poly 160/147 default Kaiser 5 for 48k; arithmetic channel mean for mono; float32 ingress; .125 s digital silence per end; no fades; fixed DSP delay removed",
        acoustic_instrument="Piano recording as labeled by author; physical acoustic instrument/recording method unverified",
        baseline_commit=BASELINE, sources=sources, listening=listening)
    (args.output / "recording_provenance.json").write_text(json.dumps(provenance, indent=2, allow_nan=False)+"\n")
    (args.output / "measurements.json").write_text(json.dumps(dict(baseline_commit=BASELINE, baselines=baselines, candidates=records), indent=2, allow_nan=False)+"\n")
    hashes = {str(q.relative_to(args.output)): file_hash(q) for q in sorted(args.output.rglob("*")) if q.is_file()}
    (args.output / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2)+"\n")


if __name__ == "__main__":
    main()
