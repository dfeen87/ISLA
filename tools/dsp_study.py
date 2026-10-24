"""Deterministic research measurements through the frozen original LIVE baseline.

Run from repo: PYTHONPATH=. python tools/dsp_study.py --output <directory>
No audio hardware, capture, routing, or playback. Raw FLOAT WAVs are measurements;
RMS-matched files are listening aids, not ITU loudness-normalized references.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import math
from pathlib import Path

import numpy as np
import soundfile as sf

from dsp_study_baseline import MODES, StreamingDSP
from dsp_study_fixtures import fixtures, fixture_manifest

BASELINE_COMMIT="4eb2412682f8b3c6321ce5c8887314850ac9a697"


def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def relative(a, b):
    level = rms(b)
    return rms(a - b) / level if level else None


def render(x, rate, mode):
    dsp = StreamingDSP(rate, x.shape[1])
    dsp.select(mode)
    count = ((len(x) + dsp.delay + 511) // 512) * 512
    padded = np.pad(x, ((0, count - len(x)), (0, 0)))
    raw = np.concatenate([dsp.process_block(b) for b in padded.reshape(-1, 512, x.shape[1])])
    return raw[dsp.delay:dsp.delay + len(x)], raw


def batch_reference(x, strength):
    """Whole-signal overlap sum, independent of transport state and kernel method."""
    n, ch = x.shape
    w = np.hanning(2049)[:-1, None]
    starts = range(-1536, ((n + 511) // 512) * 512, 512)
    out = np.zeros((n + 4096, ch))
    norm = np.zeros((n + 4096, 1))
    for start in starts:
        frame = np.zeros((2048, ch))
        lo, hi = max(0, start), min(n, start + 2048)
        frame[lo - start:hi - start] = x[lo:hi]
        z = np.fft.rfft(frame * w, axis=0)
        m = np.abs(z)
        p = np.pad(m, ((1, 1), (0, 0)))
        sm = (1 - strength / 2) * m + strength / 4 * (p[:-2] + p[2:])
        reconstructed = np.fft.irfft(sm * np.exp(1j * np.angle(z)), n=2048, axis=0) * w
        dest = start + 1536
        out[dest:dest + 2048] += reconstructed
        norm[dest:dest + 2048] += w * w
    return (out / np.maximum(norm, 1e-8))[1536:1536 + n]


def spectral(x, rate):
    frames = np.lib.stride_tricks.sliding_window_view(x, 2048, axis=0)[::512]
    z = np.fft.rfft(frames * np.hanning(2049)[:-1], axis=-1)
    mag = np.abs(z)
    f = np.fft.rfftfreq(2048, 1 / rate)
    total = float(mag.sum())
    power = np.mean(mag * mag, axis=(0, 1))
    denom = float(power.sum())
    return dict(centroid_hz=float((mag * f).sum() / total) if total else None,
                band_energy_fraction=[float(power[(f >= a) & (f < b)].sum() / denom)
                                      if denom else None for a, b in [(0, 200), (200, 2000),
                                                                    (2000, 6000), (6000, rate / 2 + 1)]])


def envelope(x, rate):
    power = np.mean(np.square(x, dtype=np.float64), axis=1)
    width = max(1, round(.001 * rate))
    return np.sqrt(np.convolve(power, np.ones(width) / width, mode="same"))


def corr(x):
    if x.shape[1] < 2 or np.min(np.std(x,axis=0)) == 0:
        return None
    return float(np.corrcoef(x.T)[0, 1])


def f0_acf(x, rate):
    """Diagnostic only: 0.2 s loudest frame autocorrelation, 70--1000 Hz."""
    y = x.mean(axis=1).astype(float)
    width = round(.2 * rate)
    candidates = range(0, len(y) - width, width // 2)
    start = max(candidates, key=lambda i: rms(y[i:i + width]))
    frame = y[start:start + width] * np.hanning(width)
    if rms(frame) < 1e-10:
        return None
    z = np.fft.rfft(frame, n=2 * width)
    ac = np.fft.irfft(z * z.conj())[:width]
    lo, hi = int(rate / 1000), int(rate / 70)
    k = lo + np.argmax(ac[lo:hi])
    a, b, c = ac[k - 1:k + 2]
    shift = .5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0
    return float(rate / (k + shift))


def onset_offsets(a, b, rate):
    """Match strongest reference envelope rises separated by >=100 ms."""
    da, db = np.diff(envelope(a, rate)), np.diff(envelope(b, rate))
    if db.max(initial=0) < 1e-10:
        return []
    chosen = []
    for i in np.argsort(db)[::-1]:
        if db[i] < .25 * db.max() or len(chosen) >= 12:
            break
        if all(abs(i - j) > .1 * rate for j in chosen):
            chosen.append(int(i))
    window = round(.025 * rate)
    return [float((max(0, i - window) + np.argmax(da[max(0, i-window):i+window+1]) - i)
                  / rate * 1000) for i in chosen]


def waveform_lag(a,b):
    """Maximum whole-passage correlation within +/-512 samples; no pitch claim."""
    if not rms(a) or not rms(b): return None
    nfft=1 << (2*len(a)-1).bit_length()
    z=np.sum(np.fft.rfft(a,n=nfft,axis=0)*np.fft.rfft(b,n=nfft,axis=0).conj(),axis=1)
    ac=np.fft.irfft(z,n=nfft)
    lags=np.arange(-512,513)
    return int(lags[np.argmax(ac[lags % nfft])])


def metrics(y, dry, rate, raw):
    a, b = y.astype(float), dry.astype(float)
    ra, rb = rms(a), rms(b)
    gain = rb / ra if ra else 1.
    matched = a * gain
    dot = float(np.sum(a * b))
    optimal = dot / float(np.sum(a * a)) if ra else 1.
    diff = np.diff(a, axis=0)
    # Output-hop edges expressed after removal of the 1536-frame delay.
    seams = np.arange(511, len(diff), 512)
    return dict(relative_rms=relative(a, b), rms=ra,
                rms_gain_db=20*np.log10(ra/rb) if ra and rb else None,
                rms_match_gain=gain, matched_relative_rms=relative(matched, b),
                optimal_gain_residual=relative(a * optimal, b),
                peak=float(np.max(np.abs(a))), raw_peak=float(np.max(np.abs(raw))),
                samples_over_fullscale=int(np.sum(np.abs(a) > 1)),
                raw_samples_over_fullscale=int(np.sum(np.abs(raw) > 1)),
                crest_factor_db=20*np.log10(np.max(np.abs(a))/ra) if ra else None,
                stereo_correlation=corr(a),
                stereo_correlation_delta=(corr(a)-corr(b)) if corr(a) is not None and corr(b) is not None else None,
                envelope_relative_rms=relative(envelope(a, rate), envelope(b, rate)),
                matched_envelope_relative_rms=relative(envelope(matched,rate),envelope(b,rate)),
                waveform_correlation_lag_samples=waveform_lag(a,b),
                onset_offsets_ms=onset_offsets(a, b, rate),
                seam_max_step=float(np.max(np.abs(diff[seams]))),
                all_max_step=float(np.max(np.abs(diff))),
                seam_rms_step=rms(diff[seams]), all_rms_step=rms(diff),
                **spectral(a, rate))


def diagnostics():
    from isla.harmonics import HarmonicBlender
    records = []
    for rate in (44100, 48000):
        for hz in (40, 100, 220, 440, 1000, 5000, 10000, 18000):
            for harmonics in (1, 8):
                t = np.arange(rate) / rate
                x = sum(np.sin(2*np.pi*hz*k*t)/k for k in range(1, harmonics+1) if hz*k < rate/2)
                x *= .2/max(abs(x))
                x = np.pad(x, (4096,4096)).astype(np.float32)[:,None]
                y, _ = render(x,rate,"melt")
                records.append(dict(rate=rate,hz=hz,harmonics=harmonics,
                                    relative_rms=relative(y,x), matched_relative_rms=relative(y*rms(x)/rms(y),x),
                                    gain_db=20*np.log10(rms(y)/rms(x))))
    rng = np.random.default_rng(171)
    x = rng.normal(0,.1,(16384,2)).astype(np.float32)
    y,_ = render(x,48000,"melt")
    scale_errors=[]
    for scale in (.001,.1,3):
        scaled,_=render(x*scale,48000,"melt")
        scale_errors.append(dict(scale=scale,max_error=float(np.max(abs(scaled-y*scale)))))
    mag = rng.uniform(0,10,(2,1025))
    exact=[]
    for strength in (.35,.55,.75):
        p=np.pad(mag,((0,0),(1,1)))
        wanted=(1-strength/2)*mag+strength/4*(p[:,:-2]+p[:,2:])
        actual=HarmonicBlender(strength)._smooth_harmonics(mag)
        exact.append(dict(strength=strength,max_kernel_error=float(np.max(abs(actual-wanted)))))
    # Cold start is intentionally separate from fixture silence pre-roll.
    startup=[]
    for rate in (44100,48000):
        for ch in (1,2):
            for signal in ("dc_step","impulse","sine_440"):
                x=np.full((8192,ch),.5,np.float32)
                if signal=="impulse": x[1:]=0
                if signal=="sine_440": x[:]=(.5*np.sin(2*np.pi*440*np.arange(len(x))/rate))[:,None]
                for mode in MODES:
                    aligned,raw=render(x,rate,mode)
                    startup.append(dict(rate=rate,channels=ch,signal=signal,mode=mode,
                        raw_peak=float(np.max(abs(raw))), pre_delay_peak=float(np.max(abs(raw[:1536]))),
                        over_fullscale=int(np.sum(abs(raw)>1)), aligned_peak=float(np.max(abs(aligned)))))
    return dict(frequency_sensitivity=records, amplitude_homogeneity=scale_errors,
                kernel_formula=exact,cold_start=startup)


def recording_sources(paths,rate,ch):
    """Deterministic common passages; resampling/downmix precedes all mode paths."""
    from scipy.signal import resample_poly
    sources={}; metadata=[]
    for path in paths:
        x,native_rate=sf.read(path,dtype="float64",always_2d=True)
        assert x.shape[1] in (1,2) and np.isfinite(x).all()
        starts=[0.,24.] if len(x)/native_rate>=40 else [0.]
        for start in starts:
            end=min(start+12.,len(x)/native_rate)
            clip=x[round(start*native_rate):round(end*native_rate)]
            conversion="native channels"
            if ch==1 and clip.shape[1]==2:
                clip=clip.mean(axis=1,keepdims=True)
                conversion="arithmetic mean of original L/R"
            elif ch==2 and clip.shape[1]==1:
                clip=np.repeat(clip,2,axis=1)
                conversion="dual mono from original mono"
            if native_rate!=rate:
                factor=math.gcd(native_rate,rate)
                clip=resample_poly(clip,rate//factor,native_rate//factor,axis=0)
            # Guards isolate steady WOLA measurements; cold-start probes remain separate.
            guard=max(4096,round(.125*rate))
            clip=np.pad(clip,((guard,guard),(0,0))).astype(np.float32)
            name=f"{path.stem.lower().replace(' ','_')}_{int(start):02d}s"
            sources[name]=clip
            metadata.append(dict(fixture=name,original_filename=path.name,
                original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                native_rate=native_rate,source_start_s=start,source_end_s=end,
                target_rate=rate,channels=ch,channel_conversion=conversion,
                resampler="scipy.signal.resample_poly default Kaiser window (5.0)" if native_rate!=rate else "none",
                gain="unaltered source gain; no peak/RMS normalization",guard_frames=guard))
    return sources,metadata


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--recording",type=Path,nargs="*",default=[])
    parser.add_argument("--recordings-only",action="store_true")
    args=parser.parse_args()
    if args.recordings_only and not args.recording:
        parser.error("--recordings-only requires --recording WAV paths")
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    (out/"audio"/"raw").mkdir(parents=True,exist_ok=True)
    (out/"audio"/"rms_matched").mkdir(parents=True,exist_ok=True)
    rows=[]; pairs=[]; manifest=[]
    summary=[]; source_metadata=[]
    for rate in (44100,48000):
        for ch in (1,2):
            source_metadata.append(fixture_manifest(rate,ch))
            sources={} if args.recordings_only else fixtures(rate,ch)
            if args.recording:
                recordings,recording_metadata=recording_sources(args.recording,rate,ch)
                sources.update(recordings);source_metadata.extend(recording_metadata)
            for name,x in sources.items():
                x=np.asarray(x,np.float32)
                manifest.append(dict(rate=rate,channels=ch,fixture=name,frames=len(x),
                    sha256=hashlib.sha256(x.tobytes()).hexdigest(),peak=float(np.max(abs(x)))))
                banks={mode:render(x,rate,mode) for mode in MODES}
                dry=banks["bypass"][0]
                assert np.array_equal(dry,x), (rate,ch,name,"bypass")
                for mode,(y,raw) in banks.items():
                    row=dict(rate=rate,channels=ch,fixture=name,mode=mode,**metrics(y,dry,rate,raw))
                    if name in ("simple_tone","harmonic_sustain"):
                        row["acf_f0_hz"]=f0_acf(y,rate)
                    if mode!="bypass":
                        ref=batch_reference(x,dict(velvet=.35,legato=.55,melt=.75)[mode])
                        row["independent_wola_max_error"]=float(np.max(abs(y-ref)))
                        assert np.allclose(y,ref,atol=1e-7,rtol=1e-6),(rate,ch,name,mode)
                    rows.append(row)
                    if rate==48000 and ch==2 and (args.recordings_only or name in ("solo_piano","connected_melody","dense_mix","percussion")):
                        sf.write(out/"audio"/"raw"/f"{name}_{mode}.wav",y,rate,subtype="FLOAT")
                        # Same source/time/gain convention for every mode, includes original Bypass.
                        matched=y*row["rms_match_gain"]
                        sf.write(out/"audio"/"rms_matched"/f"{name}_{mode}.wav",matched,rate,subtype="FLOAT")
                wet=[banks[m][0].astype(float) for m in MODES[1:]]
                summary.append(dict(rate=rate,channels=ch,fixture=name,
                    midpoint_max_error=float(np.max(abs(wet[1]-(wet[0]+wet[2])/2))),
                    baseline_zero_error=float(np.max(abs(dry-x)))))
                for i,m in enumerate(MODES):
                    for n in MODES[i+1:]:
                        a,b=banks[m][0].astype(float),banks[n][0].astype(float)
                        gain=rms(b)/rms(a) if rms(a) else 1.
                        pairs.append(dict(rate=rate,channels=ch,fixture=name,a=m,b=n,
                            relative_rms=relative(a,b),rms_matched_relative_rms=relative(a*gain,b)))
                print(f"measured {rate} Hz {ch}ch {name}",flush=True)
    root=Path(__file__).resolve().parents[1]
    try:
        checkout_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):
        checkout_commit=None  # Source archives intentionally contain no .git.
    production_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [root/"isla/streaming.py",root/"isla/harmonics.py",root/"phased_music_notes/harmonics.py"]}
    metadata=dict(kind="deterministic-identical-source-live-study",baseline_commit=BASELINE_COMMIT,
        checkout_commit=checkout_commit,checkout_source_sha256=production_hashes,
        rendering_implementation="frozen original tools/dsp_study_baseline.py; not current production DSP",
        baseline_reference_sha256=hashlib.sha256((root/"tools/dsp_study_baseline.py").read_bytes()).hexdigest(),
        platform=platform.platform(),
        python=platform.python_version(),numpy=np.__version__,soundfile=sf.__version__,
        bands_hz=["0-200","200-2000","2000-6000","6000-Nyquist"],
        alignment="1536 frames removed; full raw output separately inspected for cold-start probes",
        fixture_provenance="Original deterministic synthesis and/or explicitly supplied licensed recordings; see source_metadata and recording provenance",
        measurements=rows,pairwise=pairs,invariants=summary,fixtures=manifest,
        source_metadata=source_metadata,diagnostics=diagnostics())
    (out/"measurements.json").write_text(json.dumps(metadata,indent=2,allow_nan=False)+"\n")
    for filename,records in [("measurements.csv",rows),("pairwise.csv",pairs),("fixtures.csv",manifest)]:
        columns=list(dict.fromkeys(k for r in records for k in r))
        with (out/filename).open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(records)
    print(f"wrote {len(rows)} mode measurements and {len(pairs)} pair comparisons",flush=True)


if __name__=="__main__":
    main()
