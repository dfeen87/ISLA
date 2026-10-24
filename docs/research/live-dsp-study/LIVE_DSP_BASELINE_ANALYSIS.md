# LIVE DSP baseline analysis

ISLA — SOL ULTRA · V3.0 controlled study · October 24, 2026 (America/New_York)

**Conclusion: LIVE Velvet, Legato and Melt are three intensities of one spectral-magnitude operation.** There is no additional mode-specific attack, note-connection or harmonic-relationship algorithm. Their similar character is mathematically expected. This does not imply that every remaining difference is inaudible, or that the owner's preference for Melt is invalid.

Baseline: [`4eb2412682f8b3c6321ce5c8887314850ac9a697`](https://github.com/dfeen87/ISLA/commit/4eb2412682f8b3c6321ce5c8887314850ac9a697), freshly cloned from `main`. Isolated local branch: `experiment/sol-ultra-live-dsp-study`. The existing suite validated this baseline locally. Hosted final-head CI and plugin builds are separately qualified below. Production DSP, legacy imports, ALIVE, routing and v3.0.0 identity remain unchanged. Phase A inspected sources and ran probes without production edits.

## Authoritative source map

All references below are to the pinned baseline, not an inferred offline design.

| Source | Verified responsibility |
|---|---|
| [`isla/streaming.py:16–74`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/isla/streaming.py#L16-L74) | 2048/512 framing, retained WOLA, dry delay, all warm banks and switching |
| [`isla/harmonics.py`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/isla/harmonics.py) | Public forwarding import of BEDROCK's blender |
| [`phased_music_notes/harmonics.py:145–160`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/phased_music_notes/harmonics.py#L145-L160) | Actual three-tap magnitude kernel used by LIVE |
| [`phased_music_notes/smoother.py`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/phased_music_notes/smoother.py) | Separate offline boundary interpolation, 12/25/40 ms presets and different curves; not invoked by LIVE |
| [`isla/live.py:187–258`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/isla/live.py#L187-L258) | Callback ring transport, worker DSP, meters, failure handling and routing checks |
| [`tests/test_live.py:244–329`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/tests/test_live.py#L244-L329) | Batch WOLA reference, Bypass and switching checks; reference comparison discards the first 1536 emitted samples |
| [`IMPLEMENTATION_AND_ACCEPTANCE.md`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md), [`OWNER_LISTENING_FOLLOWUP.json`](https://github.com/dfeen87/ISLA/blob/4eb2412682f8b3c6321ce5c8887314850ac9a697/docs/alive/OWNER_LISTENING_FOLLOWUP.json) | Historical native observations and owner Melt preference; not a same-passage controlled comparison at this study head |

Some harmonic-module prose mentions spectral tilt, low-pass and transient softening. Those descriptions do not implement extra processing: the executable LIVE kernel is the operation derived next.

## Exact transfer behavior

For each channel and analysis frame, let `N=2048`, `H=512`, `K=N/2=1024`, and let the periodic Hann be

\[
w[n]=\tfrac12-\tfrac12\cos(2\pi n/N),\qquad X[k]=\operatorname{rFFT}(w x)[k],\quad M[k]=|X[k]|.
\]

With zero extension `M[-1]=M[K+1]=0`, the actual strength blend is

\[
M_s[k]=(1-s/2)M[k]+(s/4)(M[k-1]+M[k+1])
=M[k]+\frac{s}{4}\bigl(M[k-1]-2M[k]+M[k+1]\bigr).
\]

| Profile | Strength | Center coefficient | Each adjacent bin |
|---|---:|---:|---:|
| Velvet | 0.35 | 0.825 | 0.0875 |
| Legato | 0.55 | 0.725 | 0.1375 |
| Melt | 0.75 | 0.625 | 0.1875 |

This measures **local curvature across spectral bins**, not harmonic identity or absolute audio frequency. Interior flat or linear magnitude sequences are fixed points. Peaks lose magnitude; nearby troughs gain it. An isolated one-bin magnitude peak follows the table, but a Hann-windowed sinusoid spans several bins, so these coefficients are not whole-signal tone gains.

The response to variation along the magnitude-bin index is

\[
G_s(\theta)=1-s\sin^2(\theta/2).
\]

At alternating-bin variation, the gains are 0.65/0.45/0.25. Here `theta` is a modulation frequency *along the spectrum*, not audio frequency. This is not an audio low-pass filter. At the rFFT endpoints, zero extension removes total magnitude `s(M[0]+M[K])/4`; no mirrored-edge compensation exists. Magnitude sums are not audio power or loudness.

| Quantity | 44.1 kHz | 48 kHz |
|---|---:|---:|
| Bin spacing / one-neighbor reach | 21.533203125 Hz | 23.4375 Hz |
| Window duration | 46.4399 ms | 42.6667 ms |
| Hop / worker budget | 11.6100 ms | 10.6667 ms |
| Nominal 1536-frame DSP delay | 34.8299 ms | 32.0000 ms |

Widely spaced musical partials are not explicitly blended with one another. Rate changes alter the kernel's physical bandwidth and temporal span. Quiet/loud differentiation, pitch detection, onset detection and separate temporal attack/release behavior are absent.

## Why the modes have the same character

For fixed input, phase, frame coordinates and state initialization, reconstruction and WOLA normalization are linear in strength:

\[
y_s=y_0+s d,\qquad y_{0.55}=\tfrac12(y_{0.35}+y_{0.75}).
\]

Thus both adjacent mode increments are `0.2 d`. There is one source-dependent change direction, not three independently shaped transformations. Across the controlled corpus, the maximum midpoint residual was **2.24e-8** full scale for synthetic sources and **4.47e-8** for the CC0 passages, consistent with float32 rounding.

This operator is positively homogeneous in exact arithmetic. It is nonlinear in mixed inputs because magnitudes and phases depend on the mixture. In finite precision, gain changes can perturb nearly empty bin phases: the edge harness found zero scaling error for its power-of-two controls, but nonzero decimal-gain sensitivity near spectral nulls. No amplitude-compressor interpretation is supported.

## Phase: preservation and a verified limitation

Reconstruction is `Z_s[k]=M_s[k] exp(i arg X[k])`. The angle of a nonzero original coefficient is retained; there is no bin relocation or resampling inside LIVE. This does not guarantee identical phase after reanalysis of the final WOLA waveform, unchanged stereo image, or unchanged onsets.

At a spectral null, the original angle is undefined (`angle(0)=0` in this path). A near-null angle may be dominated by quantization/noise, yet neighbor smoothing can give that bin appreciable magnitude. As `X[k]` approaches zero from different directions, reconstructed phase can change while the borrowed magnitude remains nonzero. The mapping is therefore discontinuous at such nulls.

Reproducible edge probe: 65,536 samples, peak-0.5 sinusoid, 4096 samples cropped from both ends, seeded Gaussian perturbation before float32 conversion. At 48 kHz mono, a bin-centered **468.75 Hz** Melt output changed **10.91% RMS** when input changed only **3.08e-8 relative RMS** (noise standard deviation `1e-8`, seed 72). The 937.5 Hz probe changed 11.42%. Both rates and proportional stereo were tested; the largest stereo case at noise standard deviation `1e-8` was about 11.92%, with correlation near 1 falling to about 0.99326. Off-bin 220/440/1000 Hz controls were far less sensitive.

These are numerical robustness findings, not claims that the noise is audible or that the owner heard artifacts. They are also not a sufficient basis to increase smoothing strength.

## WOLA: steady reconstruction and startup overshoot

The wet path sums inverse-transform frames multiplied by the synthesis Hann, divided by the accumulated squared-window sum:

\[
y_s[t]=\frac{\sum_j w[t-jH]\,\operatorname{irFFT}(Z_{s,j})[t-jH]}{\max(\sum_j w^2[t-jH],10^{-8})}.
\]

For four complete overlaps, the denominator is **3/2** (numerical range `1.4999999999999996–1.5000000000000007`). A zero-strength control reconstructs the aligned source; the normalization itself does not cause an unexplained steady level modulation. The measured attenuation in musical examples is from the spectral modification and reconstruction.

At initialization, the first three emitted blocks represent prehistory and lack complete normalization weights. Modified spectra can leak into that region. Dividing by small weights amplifies this leakage; the 5 ms initial fade does not guarantee headroom.

For immediate peak-0.5 constant input, with mode selected before the first hop, full emitted-output peaks are:

| Rate | Velvet | Legato | Melt |
|---|---:|---:|---:|
| 44.1 kHz | 0.578086 | 0.908422 | **1.238757** |
| 48 kHz | 0.529913 | 0.832720 | **1.135527** |

The peak occurs at emitted sample 7, before dry input emerges at sample 1536. A peak-0.5 **20 Hz cosine** also produces Melt peaks **1.144525 / 1.062760**. These values are not clipped internally, but can overload a downstream output. With 8192 samples of silent pre-roll, the constant-input Melt peak is about 0.460507 and the oversized transient disappears. Ordinary transform pre-response remains; it must not be confused with the startup normalization amplification.

The existing batch-reference test crops away the pre-delay interval, so a passing reference check does not establish startup safety. The separate [edge-case data](study/baseline_edge_cases.json) retains the entire emitted interval. This is a baseline issue, not a regression introduced by this study.

## Warm banks, Bypass and stereo

All three banks advance every hop even during Bypass. Selecting a mode publishes a string; the worker applies a linear crossfade using retained banks. The fade is 220 samples at 44.1 kHz and 240 at 48 kHz. The extra safety matrix found exact retained-state agreement with always-running references over **128,000 comparisons** and maximum output crossfade error **2.92e-8**. There is no evidence of stale banks causing the subtle differentiation.

Bypass uses its own float32 delay buffer. All tested finite float32 numerical sample values, including subnormals and peaks outside ±1, were preserved exactly after alignment. Literal bit identity has one qualification: summation canonicalizes negative zero to positive zero. This has no acoustic consequence but makes an unqualified all-bit-pattern claim inaccurate. Float64 inputs are converted at ingress; nonfinite hops are deliberately muted as a whole; a transition to Bypass remains mixed during the fade.

Channels are processed independently with common timing and no crossfeed. This prevents channel mixing but does not mathematically preserve correlation for arbitrary stereo mixtures. Whole-passage correlation changes reached about **0.01587** in the CC0 corpus; local spatial perception was not evaluated.

## Material sensitivity and acceptance boundary

At 48 kHz stereo, Melt's raw / RMS-matched differences were **12.05% / 0.57%** on a simple tone, **12.06% / 1.29%** on harmonic sustain, **0.41% / 0.41%** on an impulse, and **9.94% / 5.48%** on the dense synthetic mixture. A sharp impulse is nearly a fixed point of a flat-magnitude kernel, so generic transient softening is not established. Harmonic richness alone does not predict sensitivity. Grid alignment, spectral curvature, phase and temporal structure matter.

The CC0 passages retain larger matched differences, about **5.48–6.71%** for Melt across the tested formats. These must not be dismissed as pure gain or promoted as perceptual quality. See [controlled results](MODE_DIFFERENTIATION_RESULTS.md), [experiment decision](DSP_EXPERIMENT_REPORT.md) and [test/native status](TEST_AND_REGRESSION_SUMMARY.md).
