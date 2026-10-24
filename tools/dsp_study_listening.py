"""Prepare integrated-loudness comparisons from measured, unmodified raw WAVs.

Requires research-only pyloudnorm==0.2.0. Uses default BS.1770 K weighting,
400 ms gated integrated meter; remeasures every scalar-gain output. Does not
change production DSP, dynamically normalize, limit, or open an audio device.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import resample_poly


def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True)
    args=p.parse_args();root=args.input
    target=root/"audio"/"loudness_matched";target.mkdir(parents=True,exist_ok=True)
    records=[]
    for reference in sorted((root/"audio"/"raw").glob("*_bypass.wav")):
        name=reference.stem.removesuffix("_bypass")
        ref,rate=sf.read(reference,always_2d=True)
        meter=pyln.Meter(rate)
        loudness=meter.integrated_loudness(ref)
        assert np.isfinite(loudness)
        loaded=[]
        for mode in ("bypass","velvet","legato","melt"):
            rawpath=reference.with_name(f"{name}_{mode}.wav")
            x,sr=sf.read(rawpath,always_2d=True)
            assert sr==rate and x.shape==ref.shape
            before=meter.integrated_loudness(x)
            loaded.append((mode,rawpath,x,before))
        # Common reduction preserves fidelity measurements and gives listening
        # copies headroom even if a source or raw wet output reaches full scale.
        target_lufs=min(loudness-3.,-23.)
        predicted_peak=max(float(np.max(abs(x)))*10**((target_lufs-before)/20)
                           for _,_,x,before in loaded)
        if predicted_peak>.85:
            target_lufs+=20*np.log10(.85/predicted_peak)
        for mode,rawpath,x,before in loaded:
            gain=10**((target_lufs-before)/20)
            y=(x*gain).astype(np.float32)
            path=target/rawpath.name
            sf.write(path,y,rate,subtype="FLOAT")
            saved,_=sf.read(path,always_2d=True)
            after=meter.integrated_loudness(saved)
            assert abs(after-target_lufs)<.01
            peak=float(np.max(abs(saved)))
            # 4x polyphase peak probe, not a certified BS.1770 true-peak meter.
            oversampled_peak=float(np.max(abs(resample_poly(saved,4,1,axis=0))))
            assert max(peak,oversampled_peak)<1
            records.append(dict(fixture=name,mode=mode,rate=rate,frames=len(x),
                raw_integrated_lufs=float(before),reference_lufs=float(loudness),
                target_lufs=float(target_lufs),
                matched_integrated_lufs=float(after),gain_db=float(20*np.log10(gain)),
                sample_peak=peak,oversampled_4x_peak_probe=oversampled_peak,
                path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (root/"listening_loudness.json").write_text(json.dumps(dict(
        meter="pyloudnorm default BS.1770 K-weighting, 400 ms, absolute/relative gates",
        pyloudnorm=importlib.metadata.version("pyloudnorm"),
        reference="shared passage target <= Bypass minus 3 LU and <= -23 LUFS, with common headroom reduction if needed; same scalar both channels",
        peak_note="4x resample_poly peak is a probe, not a certified true-peak result",
        records=records),indent=2)+"\n")
    print(f"Prepared and verified {len(records)} loudness-matched WAVs")


if __name__=="__main__":main()
