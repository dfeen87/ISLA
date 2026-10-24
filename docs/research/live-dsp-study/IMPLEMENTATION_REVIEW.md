# LIVE numerical corrections — implementation review

October 24, 2026 · ISLA 3.0.0 · experimental branch `experiment/sol-ultra-live-dsp-study`

**Recommendation: GO for code review of the two numerical corrections; MORE EVIDENCE NEEDED for independent musical identities and native acceptance. No artistic retuning or release is accepted.**

This follows the completed [baseline study](LIVE_DSP_BASELINE_ANALYSIS.md), its [controlled measurements](MODE_DIFFERENTIATION_RESULTS.md) and [research decision](DSP_EXPERIMENT_REPORT.md). Those reports and original data remain unchanged evidence for main `4eb2412682f8b3c6321ce5c8887314850ac9a697`; study commit `f9e0c13` preserves that production behavior. The corrections below deliberately change numerical edge behavior. They do not establish better listening quality.

## Findings distinguished

| Observation | Classification / action |
|---|---|
| Missing startup WOLA support amplifies modified-frame leakage | Reproduced defect; initialize the weights of virtual silent prior frames |
| Finite borrowed magnitude inherits undefined/nearly undefined phase at a null | Reproduced numerical discontinuity; bound only the spectral correction using float32 ingress precision |
| `exp(iπ)` leaves tiny imaginary DC/Nyquist residues | Expected numerical behavior; `irfft` discards them. Exact time samples are identical after removal, so no endpoint-only fix was justified |
| Kernel zero-extension treats DC/Nyquist magnitude edges differently | Existing specified kernel behavior, retained; not presumed a defect |
| Legato is the midpoint of Velvet/Melt | Expected strength-only design, retained; not a selector/bank failure |
| Owner previously preferred Melt | Historical subjective evidence; no new preference or quality verdict inferred |

## Regression tests before corrections

The startup test file was written and executed against unchanged production DSP: **48 failed, 4 passed**. After the startup-only correction, all **52 passed**. It compares complete emitted output, including pre-delay samples, against an independent complete-prehistory WOLA sum; it covers both rates, mono/stereo, all wet modes, phase and impulse-offset grids, early switches, fixed state and Bypass.

The spectral test file was also written and executed before its correction: **24 failed, 3 passed**. The 24 failures cover two rates × two channel counts × two exact-bin frequencies × three modes, using seeded input perturbations below one float32 epsilon in relative RMS. The three initially passing real-bin controls establish that discarded imaginary endpoint residues are not an audio defect. After integration and added direct properties, **31 spectral tests pass**.

Original numerical WOLA tolerances remain **absolute 1e-7 / relative 1e-6**. The independent oracle in `tests/test_live.py` now states the intentional corrected reconstruction equation; its tolerances and other assertions were not weakened. The original reference is recoverable from the pinned Git history and [frozen research implementation](../../../tools/dsp_study_baseline.py). The research harness's initial-state assertion now checks the analytical silent-prehistory weights rather than requiring the old defective all-zero weights.

Evidence: [startup red](implementation/startup-red.log), [startup-only green](implementation/startup-green.log), [spectral red](implementation/spectral-regression-before.log), [spectral green](implementation/spectral-green.log), [integrated focused tests](implementation/integrated-green.log).

## Correction 1: complete silent prehistory weights

Keep all history and wet tails zero. Before processing, initialize the weight support of the three earlier all-zero analysis frames:

`Q[n] = Σ w[n+pH]²`, for `p=1,2,3` where `n+pH < N`, with `N=2048`, `H=512`.

Their signal contributions are zero but their synthesis weights are required. Adding the first real frame then gives the complete denominator **1.5** for the first emitted hop. Initializing the entire array to 1.5 would overcount later support and is not the chosen correction.

`Q[n]=0` for `n≥1536`; left-shifting the weights each hop removes the extra initialization support entirely after three hops. Thus this correction alone changes only emitted prehistory indices 0–1535, with no change to aligned source samples, steady processing, delay, state shape or callback work. Startup-only green tests established that scope before the spectral correction was integrated.

## Correction 2: continuous correction at spectral nulls

Keep the magnitude kernel and strengths 0.35/0.55/0.75. Let `X` be the original rFFT coefficient, `M=|X|`, `M_s` the existing smoothed magnitude and `wx` the windowed input. For each channel:

`τ = ε32 · Σ|wx| + (N/2) · η32`

`P = X / max(M, τ)`

`Z_s = X + (M_s − M) · P`

`ε32` is float32 machine epsilon; `η32` is its smallest positive subnormal. The triangle inequality gives a conservative coefficient uncertainty bound for per-sample float32 ingress representation error. The absolute term covers subnormal rounding; Hann weights are at most one. This is **not** an estimate of actual FFT roundoff, a signal-noise detector, a musical cutoff or an audibility threshold.

Above `τ`, reconstruction equals the old magnitude/phase formula to arithmetic roundoff. Below `τ`, the borrowed correction tends continuously to zero with `X`; a true null receives no arbitrary finite-phase energy. Keeping the original `X` separately preserves zero-strength complex identity. Valid rFFT DC/Nyquist coefficients remain real through this real-gain correction without a new endpoint policy. The shared phase reference is computed once per frame and reused across all three banks.

Production changes are confined to [streaming state/reconstruction](../../../isla/streaming.py) and the small [LIVE-only helper](../../../isla/spectral.py). Offline harmonics, ALIVE, legacy imports, public constructor/modes, callback/routing, window/hop/delay and version metadata remain unchanged. No new temporal musical state, lookahead, note detector or strength parameter was added.

## Before/after results

### Whole emitted startup, Melt, peak-0.5 input

| Source / rate | Original peak | Both corrections peak |
|---|---:|---:|
| Immediate constant / 44.1 kHz | 1.238757 | 0.458413 |
| Immediate constant / 48 kHz | 1.135527 | 0.458413 |
| Immediate 20 Hz cosine / 44.1 kHz | 1.144525 | 0.461882 |
| Immediate 20 Hz cosine / 48 kHz | 1.062760 | 0.473452 |
| Impulse / either rate | 0.499908 | 0.499908 |

Mono and stereo pass the complete-prehistory reference. These probes reject the reproduced amplification; they are not a universal peak/no-clipping guarantee for arbitrary input.

### Null sensitivity and ordinary material

The selected reconstruction's representation-scale (`1e-8` standard deviation) perturbation changes exact-bin Melt output by about **0.063–0.087% RMS**, versus **10.15–11.92%** originally across the tested rate/channel/bin configurations. Runtime regressions pass the new <1% numerical-stability screen; this screen is not an audibility threshold.

Unperturbed exact-bin tones themselves can change by about **8%** because arbitrary null-bin energy is removed. This is an intentional edge correction, not a promise of identical sound on every source. At larger `1e-6` noise standard deviation, output sensitivity still reaches **5.37–6.32%** in the probe: the correction is not denoising or a globally nonexpansive transform. The [spectral findings](implementation/SPECTRAL_SAFETY_FINDINGS.md) and [isolated formula probe](implementation/spectral_policy_probe.json) retain those limitations; the tiny absolute-subnormal term is separately tested.

The current implementation was rendered once across the same **224** mode/format/source cases, reusing original input hashes, baseline metrics and cached baseline WAVs. All input hashes match. Complete corrected WOLA reference error is at most **2.98e-8 full scale**, within unchanged tolerances. All non-silent whole-passage correlation lags remain zero samples after the fixed delay alignment.

| Ordinary source, 48 kHz stereo Melt | Relative waveform difference from original output | Maximum sample difference |
|---|---:|---:|
| Piano-like synthesis | 6.83e-8 | 5.96e-8 FS |
| Dense synthetic mixture | 4.07e-8 | 4.47e-8 FS |
| Emotional Piano, 0–12 s | 3.89e-7 | 2.41e-6 FS |
| Katanga, 0–12 s | 1.45e-7 | 4.18e-7 FS |
| Katanga, 24–36 s | 1.06e-7 | 3.58e-7 FS |

The 168-wet-source isolated-formula screen found maximum relative change 4.95e-7 for synthesis and 3.90e-7 for recordings. These small measured ordinary-source differences support narrow numerical correction; they do not prove perceptual equivalence or superiority. [Current before/after data](implementation/before_after.json) includes all 224 measurements, raw-audio hashes, independent reference errors, source hashes and cold-start results. Original source conversion overshoot in Katanga Bypass is preserved and distinguished from DSP-created clipping.

## Musical differentiation decision

No independent Velvet/Legato/Melt artistic candidate is justified yet. The corrected mapping remains affine in strength: Legato is still the midpoint, with maximum corpus residual **4.47e-8 FS**. This is deliberate preservation of the artistic baseline while fixing numerical edges, not an attempt to advertise new musical identities.

The next experiment remains one controlled variable at a time: physical-frequency weighting for Velvet, a carefully bounded temporal correction for Legato only after defining a continuity target, and wider local envelope weighting for Melt after null-stability review. Each needs attack/pitch/gap/stereo safeguards and actual same-source listening. No stronger default or larger architecture was introduced.

## Audio and README

The README's **Hear the Difference** section links directly to four committed [original-baseline FLACs](../../audio/live-baseline/PROVENANCE.md). A separate [numerical-fix comparison set](../../audio/live-robustness/PROVENANCE.md) is labeled under review and is not advertised as an accepted musical improvement. All eight files use the same source seconds 2–8, common presentation fades/guards and shared −23 LUFS. PCM24 FLAC storage, constant stereo-linked gains, processing versions/source hashes, original CC0 attribution, sample rate and byte checksums are documented. Combined audio is approximately **6.82 MB**.

Full raw FLOAT measurements and 28 corrected loudness-matched listening copies remain separate local outputs; regeneration is documented below. No sample was played automatically. There is no new owner preference, ABX result or native/acoustic acceptance.

README first-run instructions now place `setup audio` immediately after the initial `isla>` example and before optional `devices`, incorporating the intended ordering from closed, unmerged PR #24. Installation, routing safety, licensing, attribution, acknowledgements and dedication remain intact. Unmerged corrections are linked as review work rather than advertised as a published release.

## Regression, performance and remaining gates

- Full Python suite: **267 passed, 1 unchanged XFAIL**, one existing Starlette/httpx deprecation warning. The XFAIL remains the legacy offline nonzero chunk-streaming limitation.
- Wheel build: **passed**, v3.0.0; archive inspection confirms the corrected streaming/helper sources are included byte-for-byte.
- Safety matrix: 2000 hops/configuration, both rates and channels, **128,000** exact warm-state comparisons, no stale banks, finite recovery from whole-hop nonfinite muting, zero numerical aligned Bypass error. Negative-zero sign canonicalization remains the documented pre-existing representation qualification.
- Retained DSP arrays: unchanged **108,576 / 180,256 bytes** mono/stereo; stereo ring/timestamp arrays **65,664 bytes**. This is not a process-RSS or native memory-growth proof.
- Budget screen: **25,200 measured hops**, no observed worker-body overrun. Loaded stereo p99/max is **0.240/0.402 ms at 44.1 kHz**, **0.263/0.391 ms at 48 kHz**, versus 11.610/10.667 ms budgets. The 1200-hop paced 48 kHz stereo cell has p99/max **0.367/0.696 ms**, maximum wakeup lateness **2.773 ms**, zero modeled completion misses. Two barrier-ready CPU competitors supply explicit load; ordinary host activity is uncontrolled.

The timing model excludes native callback/GIL scheduling, periodic route inspection, devices and physical latency. Historical baseline timing is a separate run; no speedup claim is made. Parent peak RSS includes fixture generation and excludes competitor memory. [Full timing distributions](implementation/benchmark.json), [safety data](implementation/safety.json), [suite log](implementation/pytest-full.log), and [wheel log](implementation/wheel-build.log) retain scope.

CMake/plugin sources and vendor prerequisites are unchanged. The prior configure failure from empty JUCE/pybind11 placeholders is retained as [unresolved build evidence](study/validation/cmake-configure.log), not rerun or called a pass. Hosted PR checks will separately exercise their configured dependency setup; native macOS monitoring, ≥30-minute realistic reliability, physical disconnect/recovery, acoustic latency, explicit glitch/echo and owner listening acceptance remain pending. No device route, capture, volume, merge, version bump, tag or release was performed.

## Reproduce without repeating the baseline unnecessarily

Use the existing study directory and original checksum-verified recordings. Research-only plotting/loudness dependencies are separate from package dependencies; use the prior study environment or install `pyloudnorm==0.2.0` for sample generation.

```sh
PYTHONPATH=. python tools/dsp_robustness_compare.py --study-root <existing-study-root> --output <implementation-output>
PYTHONPATH=. python tools/dsp_study_listening.py --input <implementation-output>/synthetic
PYTHONPATH=. python tools/dsp_study_listening.py --input <implementation-output>/music
PYTHONPATH=. python tools/dsp_study_safety.py --output <implementation-output>/safety.json
PYTHONPATH=. python tools/dsp_study_benchmark.py --output <implementation-output>/benchmark.json
python -m pytest -q tests
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir <wheel-output>
```

`dsp_study.py` and `dsp_study_edge_cases.py` explicitly render the frozen original reference so the old experiment remains reproducible after these corrections. `dsp_robustness_compare.py` renders current production and checks against independently stated corrected mathematics. Compact showcase regeneration and fresh-clone preparation are in each set's provenance. Do not use a native capture probe as part of automated reproduction.

**Disposition:** narrowly supported numerical fixes are ready for review with software evidence. Independent musical modes and native release acceptance still need evidence; no merge or release is authorized by these results.
