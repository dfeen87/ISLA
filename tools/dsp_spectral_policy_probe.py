"""Optional isolated reconstruction-bound experiment; no devices or mutation.

Uses normal-range signals to compare full/half epsilon bounds to the frozen
original. It deliberately omits the absolute subnormal term, tested separately
in production helper regressions. Existing results are preserved; no need to
rerun this screen merely to validate current production.
"""
from pathlib import Path
import json
import argparse
import sys

import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--recordings", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from dsp_study_fixtures import fixtures
from dsp_study import recording_sources

BASELINE = "4eb2412682f8b3c6321ce5c8887314850ac9a697"
source = (ROOT / "tools/dsp_study_baseline.py").read_text()
old = "tail += np.fft.irfft(smooth * phase, n=self.window_size, axis=0) * self.window"
assert old in source
namespace = {}
exec(compile(source, "committed_streaming", "exec"), namespace)
Legacy = namespace["StreamingDSP"]


def candidate(factor):
    new = f"""floor = {factor!r} * np.finfo(np.float32).eps * np.sum(np.abs(self.history * self.window), axis=0, keepdims=True)
            denom = np.maximum(magnitude, floor)
            unit = np.divide(spectrum, denom, out=np.zeros_like(spectrum), where=denom > 0)
            reconstructed = spectrum + (smooth - magnitude) * unit
            tail += np.fft.irfft(reconstructed, n=self.window_size, axis=0) * self.window"""
    namespace = {}
    exec(compile(source.replace(old, new), "continuous_spectral_correction", "exec"), namespace)
    return namespace["StreamingDSP"]


Stable = candidate(1.)
HalfFloor = candidate(.5)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def relative(x, y):
    return rms(x.astype(np.float64) - y) / rms(y) if rms(y) else 0.


def render(x, rate, cls, mode="melt"):
    dsp = cls(rate, x.shape[1]); dsp.select(mode)
    count = (len(x) + dsp.delay + 511) // 512 * 512
    padded = np.pad(x, ((0, count-len(x)), (0, 0)))
    raw = np.concatenate([dsp.process_block(b) for b in padded.reshape(-1, 512, x.shape[1])])
    return raw[dsp.delay:dsp.delay + len(x)]


null = []
for rate in (44100, 48000):
    for channels in (1, 2):
        for bin_index in (20, 40):
            t = np.arange(65536) / rate
            mono = (.5 * np.sin(2*np.pi*bin_index*rate/2048*t)).astype(np.float32)
            x = mono[:, None] if channels == 1 else np.stack((mono, np.float32(.6)*mono), axis=1)
            noise = np.random.default_rng(72).normal(size=x.shape)
            baseline = render(x, rate, Legacy)[4096:-4096]
            for policy, cls in (("legacy", Legacy), ("half_ulp_bound", HalfFloor), ("float32_epsilon_bound", Stable)):
                reference = render(x, rate, cls)[4096:-4096]
                for amp in (1e-8, 1e-7, 1e-6):
                    changed = (x.astype(np.float64)+amp*noise).astype(np.float32)
                    output = render(changed, rate, cls)[4096:-4096]
                    null.append(dict(rate=rate, channels=channels, bin_index=bin_index,
                        policy=policy, noise_std=amp,
                        input_change=relative(changed[4096:-4096], x[4096:-4096]),
                        output_change=relative(output, reference),
                        policy_change_vs_legacy=relative(reference, baseline)))

ordinary = []
paths = [args.recordings / f for f in ("Emotional_piano.wav", "Katanga.wav")]
for rate in (44100, 48000):
    for channels in (1, 2):
        sources = fixtures(rate, channels)
        recordings, _ = recording_sources(paths, rate, channels)
        sources.update(recordings)
        for name, x in sources.items():
            for mode in ("velvet", "legato", "melt"):
                baseline = render(x, rate, Legacy, mode)
                output = render(x, rate, Stable, mode)
                ordinary.append(dict(rate=rate, channels=channels, source=name, mode=mode,
                    candidate_vs_legacy_relative_rms=relative(output, baseline),
                    candidate_vs_legacy_max_abs=float(np.max(abs(output-baseline))),
                    candidate_peak=float(np.max(abs(output))),
                    legacy_peak=float(np.max(abs(baseline))),
                    gain_change_db=float(20*np.log10(rms(output)/rms(baseline))) if rms(baseline) else 0.))
        print("ordinary complete", rate, channels, flush=True)

endpoints = []
rng = np.random.default_rng(196)
for kind in ("random", "negative_dc", "negative_nyquist"):
    if kind == "random": frame = rng.normal(size=(2048, 2))
    elif kind == "negative_dc": frame = np.full((2048, 2), -.5)
    else: frame = np.repeat((-.5*(-1.)**np.arange(2048))[:, None], 2, axis=1)
    z = np.fft.rfft(frame, axis=0)
    m = abs(z); p = np.pad(m, ((1,1),(0,0)))
    sm = .625*m+.1875*(p[:-2]+p[2:])
    reconstructed = sm*np.exp(1j*np.angle(z))
    exactly_real = reconstructed.copy(); exactly_real[[0,-1]] = reconstructed[[0,-1]].real
    a = np.fft.irfft(reconstructed, n=2048, axis=0)
    b = np.fft.irfft(exactly_real, n=2048, axis=0)
    endpoints.append(dict(kind=kind,
        endpoint_imag_peak=float(np.max(abs(reconstructed[[0,-1]].imag))),
        irfft_max_difference=float(np.max(abs(a-b))), numerically_equal=bool(np.array_equal(a,b))))

output = args.output
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dict(baseline_commit=BASELINE, python=sys.version, numpy=np.__version__,
    policy="Z = X + (M_s-M) X/max(M, eps32*sum(abs(windowed_input)))",
    null=null, ordinary=ordinary, endpoints=endpoints), indent=2)+"\n")
print(output)
