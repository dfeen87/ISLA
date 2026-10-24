"""LIVE-only reconstruction at coefficients with uncertain input phase.

The offline harmonic kernel and public blender remain unchanged. The bound
below describes conservative float32 ingress representation uncertainty; it
is not an estimate of actual FFT roundoff, measured noise, or audibility.
"""
from __future__ import annotations

import numpy as np


def phase_reference(spectrum, magnitude, windowed_input):
    """Return X/max(|X|, tau), shared by all three LIVE strength banks.

    For each channel, the triangle inequality bounds the FFT coefficient
    error from per-sample relative input uncertainty eps32 by
    eps32 * sum(abs(windowed_input)). This conservatively envelopes ordinary
    nearest-float32 rounding. An additional half-smallest-subnormal per time
    sample covers absolute rounding uncertainty near zero. The LIVE Hann is
    in [0, 1], so using N such terms also bounds their windowed sum.

    Above tau this is the usual unit phase. Below tau its magnitude tends
    continuously to zero, so a newly borrowed magnitude cannot acquire a
    finite arbitrary phase at a coefficient null. The positive subnormal
    term also makes the silence denominator nonzero without an audio-level
    threshold. All arrays have time/frequency first and channels second.
    """
    precision = np.finfo(np.float32)
    uncertainty = float(precision.eps) * np.sum(
        np.abs(windowed_input), axis=0, keepdims=True, dtype=np.float64
    )
    uncertainty += .5 * float(precision.smallest_subnormal) * len(windowed_input)
    denominator = np.maximum(magnitude, uncertainty)
    return np.divide(spectrum, denominator, out=np.zeros_like(spectrum),
                     where=denominator > 0)


def reconstruct_spectrum(spectrum, magnitude, smoothed, reference):
    """Apply only the harmonic correction using the bounded phase reference.

    Z = X + (M_s - M) X/max(M, tau). This retains the original complex X
    exactly at zero strength and equals the legacy magnitude/phase formula
    above the uncertainty bound, to floating-point roundoff. Actual rFFT
    DC/Nyquist coefficients are real, so their correction remains real.
    """
    return spectrum + (smoothed - magnitude) * reference
