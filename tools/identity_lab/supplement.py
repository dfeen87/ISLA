"""Post-screen analysis and explicitly labeled low-Melt listening supplement.

Does not replace preregistered center files, measurements, or failed screens.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import correlate, correlation_lags

from tools.identity_lab.dsp import render
from tools.identity_lab.run import sources, save_listening, file_hash, array_hash, envelope


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--generated", type=Path, required=True)
    p.add_argument("--recorded", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    listening, diagnostics = [], []
    for source_root in (args.generated, args.recorded):
        for rawroot in sorted((source_root / "raw_float").iterdir()):
            x, rate = sf.read(rawroot / "source.wav", dtype="float32", always_2d=True)
            original, _ = sf.read(rawroot / "melt_original.wav", dtype="float32", always_2d=True)
            bypass, _ = sf.read(rawroot / "bypass.wav", dtype="float32", always_2d=True)
            y, _ = render(x, rate, "melt", {"melt": .15})
            # Same target rule as the fixed showcase. All originals are retained
            # alongside this supplementary amount so matching is auditable.
            records = save_listening(args.output, rawroot.name,
                {"bypass": bypass, "melt_original": original, "melt_low_experiment": y}, rate)
            listening.extend(records)
            rawout = args.output / "raw_float" / rawroot.name
            rawout.mkdir(parents=True)
            sf.write(rawout / "melt_low_experiment.wav", y, rate, subtype="FLOAT")
    source, rate = sf.read(args.recorded / "Emotional_piano.wav", always_2d=True)
    for profile, amount, channels in [("legato", .50, 2), ("melt", .30, 1), ("melt", .45, 2)]:
        x = source[2*rate:8*rate]
        if channels == 1:
            x = x.mean(axis=1, keepdims=True)
        x = np.pad(x, ((round(.125*rate), round(.125*rate)), (0, 0))).astype(np.float32)
        original, _ = render(x, rate, profile)
        candidate, _ = render(x, rate, profile, {profile: amount})
        da, db = np.diff(envelope(candidate, rate)), np.diff(envelope(original, rate))
        chosen = []
        for i in np.argsort(db)[::-1]:
            if db[i] < .25 * db.max() or len(chosen) >= 12:
                break
            if all(abs(i - j) > .1 * rate for j in chosen):
                chosen.append(int(i))
        radius = round(.025 * rate)
        for i in chosen:
            j = max(0, i-radius) + int(np.argmax(da[max(0,i-radius):i+radius+1]))
            if abs(j-i) <= .001 * rate:
                continue
            lo, hi = max(0, min(i,j)-round(.03*rate)), min(len(x), max(i,j)+round(.03*rate))
            a, b = candidate[lo:hi].mean(axis=1), original[lo:hi].mean(axis=1)
            corr = correlate(a, b, mode="full", method="fft")
            lags = correlation_lags(len(a), len(b))
            keep = abs(lags) <= radius
            lag = int(lags[keep][np.argmax(corr[keep])])
            diagnostics.append(dict(profile=profile, amount=amount, rate=rate, channels=channels,
                reference_peak_seconds=i/rate, candidate_peak_seconds=j/rate,
                picked_shift_ms=(j-i)/rate*1000, local_waveform_correlation_lag_samples=lag,
                original_slope_at_reference=float(db[i]), original_slope_at_candidate=float(db[j]),
                candidate_slope_at_reference=float(da[i]), candidate_slope_at_candidate=float(da[j]),
                time_seconds=(np.arange(lo,hi-1)/rate).tolist(),
                original_envelope_slope=db[lo:hi-1].tolist(), candidate_envelope_slope=da[lo:hi-1].tolist()))
    (args.output / "supplement.json").write_text(json.dumps(dict(
        purpose="Post-screen supplement: low Melt .15 is the only Melt amount passing every registered screen; center .30 remains diagnostic and failed",
        interpretation="Competing envelope-slope peaks can change ranking; local lag is diagnostic, not an override of failed screening",
        listening=listening, attack_diagnostics=diagnostics), indent=2, allow_nan=False)+"\n")
    hashes = {str(q.relative_to(args.output)): file_hash(q) for q in sorted(args.output.rglob("*")) if q.is_file()}
    (args.output / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2)+"\n")


if __name__ == "__main__":
    main()
