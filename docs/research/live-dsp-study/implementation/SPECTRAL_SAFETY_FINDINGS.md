> Historical pre-integration helper investigation. The completed integration and green regressions are documented in [the implementation review](../IMPLEMENTATION_REVIEW.md).

# LIVE spectral reconstruction correction

The committed study baseline is `f9e0c13`; its production DSP is unchanged from `4eb2412`. Tests were written and run before introducing a spectral helper. This investigation used Python3.14.6 / NumPy2.5.4 and opened no audio device.

## Failing evidence before correction

`tests/test_streaming_spectral_safety.py` initially produced **24 failed,3 passed**. The24 failures cover2 sample rates ×2 channel configurations ×2 exact-bin frequencies ×3 modes, with a seeded input perturbation below one float32 epsilon in relative RMS. The deliberately broad new regression requirement rejects output changes≥1% RMS under that representation-scale perturbation; the original operation produced changes up to11.92% in these cases. This is a numerical robustness screen, not an audibility threshold or a weakened WOLA tolerance. All tests crop4096 samples from both ends, separating persistent phase-null behavior from startup normalization.

Raw failure log: `spectral-regression-before.log`.

The three initially passing DC/Nyquist controls are consequential: the legacy `exp(i*pi)` can leave an imaginary residue up to~7.84e-14 on large real endpoint coefficients in these probes, but `irfft` discards those imaginary endpoint values. Removing that residue gives **exactly identical time samples**. No endpoint-only audible defect or separate endpoint fix is supported.

## Selected smallest correction

The magnitude kernel, strengths, framing, retained banks and offline processing remain unchanged. Reconstruct the **correction** using a continuous phase reference:

\[
\tau_c=\epsilon_{32}\sum_n|x_c[n]w[n]|+\frac{N}{2}\eta_{32},
\qquad P_c[k]=\frac{X_c[k]}{\max(M_c[k],\tau_c)},
\]

\[
Z_{s,c}[k]=X_c[k]+\bigl(M_{s,c}[k]-M_c[k]\bigr)P_c[k],
\]

where epsilon32 is float32 machine epsilon and eta32 is its smallest positive subnormal. The first term is the triangle-inequality bound for per-sample relative representation uncertainty≤epsilon32; this conservatively envelopes ordinary nearest-float32 rounding. The second adds half a smallest subnormal per sample. Hann weights are≤1, so using N such terms is conservative for absolute subnormal rounding uncertainty. These are ingress-precision uncertainty bounds, **not estimates of actual FFT truncation/roundoff, signal noise or musical salience**.

Above tau this equals the old magnitude/phase reconstruction to arithmetic roundoff. Below tau the borrowed correction tends continuously to zero with the original complex coefficient; it cannot create finite output with an undefined phase at an exact null. Keeping the original X separately preserves exact numerical zero-strength identity, unlike shrinking the entire smoothed spectrum by the regularized phase. Valid rFFT DC/Nyquist coefficients are real and remain real through the new real-gain correction without a special endpoint policy.

The policy is scale covariant for ordinary normal-range inputs; the absolute subnormal term intentionally represents a fixed quantization floor near zero. It creates no artistic cutoff, gain cap, attack/release parameter, extra lookahead or callback work. The phase reference is shared across the three strength banks.

Helper API in `isla/spectral.py`:

```python
reference = phase_reference(spectrum, magnitude, windowed_input)
reconstructed = reconstruct_spectrum(spectrum, magnitude, smoothed, reference)
```

The parent integrates this once-per-frame reference and per-bank correction into `StreamingDSP`; this agent did not edit `isla/streaming.py` or offline harmonics.

## Before/after source comparison

`spectral_policy_probe.py` dynamically loads the committed original StreamingDSP and changes only its reconstruction formula in an isolated probe class. It measures the same source arrays through both classes, with all11 synthetic sources and3 CC0 passages, both rates/channels and all3 wet modes:168 wet comparisons. Full results are in `spectral_policy_probe.json`. The original probe omits the final tiny absolute-subnormal term; that term is negligible at all these ordinary signal levels and is separately tested directly.

| Strongest ordinary-source change versus original output | Relative RMS | Max absolute sample difference |
|---|---:|---:|
| Synthetic corpus |4.9411e-7|4.1723e-7 full scale|
| CC0 corpus |3.8931e-7|2.4065e-6 full scale|

The largest CC0 sample difference is Emotional Piano at48 kHz stereo Melt. Its relative gain change is about4.6e-10 dB. The maximum synthetic relative change is the mono spectral/stereo probe at48 kHz Melt. These values support a narrow robustness correction on the measured ordinary corpus, not a universal perceptual equivalence proof.

On exact-bin tones, noise standard deviation1e-8 changes legacy Melt output by10.15–11.92% across the tested rate/channel/bin configurations. The selected full-epsilon floor reduces that to **.0627–.0866%**. The unperturbed exact-bin output itself can change about8% relative to legacy because the arbitrary newly populated null-bin energy is removed; that intentional edge behavior must remain visible in comparisons.

**Limitation:** noise standard deviation1e-6 is larger than the chosen ingress uncertainty floor in many tested bins. Output sensitivity remains **5.37–6.32%** across the tested rate/channel/bin configurations; at1e-7 it is.576–.790%. The correction establishes a continuous, bounded phase assignment around zero and improves the defined representation-scale failure. It does **not** justify a claim of general denoising, global nonexpansiveness or uniformly small response to all tiny absolute-noise levels. Larger-noise and phase/frequency sweeps remain useful acceptance data.

## Direct helper checks

After adding the helper, its direct/property subset produced **7 passed,24 deselected** (`spectral-helper-tests.log`): the three endpoint controls plus above-floor legacy equivalence, continuous approach to a null from four complex directions, zero-strength identity, silence and subnormal finite behavior. Original tolerances were not altered. Parent integration is required before the24 originally failing StreamingDSP regressions can turn green.

This correction cannot create new named musical identities: for a fixed source the reconstructed result remains affine in strength. It addresses a verified spectral representation defect while preserving the current artistic operation wherever coefficient phase is resolved by the ingress precision bound.
