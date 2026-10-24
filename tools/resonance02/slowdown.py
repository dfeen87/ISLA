"""Research-only, stereo-consistent fixed-hop phase-vocoder controls.

This implements established phase propagation, identity phase locking and a
heuristic transient reset. It is not a production or validated piano stretcher.
See docs/research/phase-governed-resonance-02/SLOWDOWN.md for frozen screens.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import resample_poly


FRAME_SIZE = 2048
ANALYSIS_HOP = 512
MAGNITUDE_FLOOR = 1e-12


def _wrap(phase: np.ndarray) -> np.ndarray:
    return (phase + np.pi) % (2.0 * np.pi) - np.pi


def _peak(signal: np.ndarray) -> float:
    return float(np.max(np.abs(signal))) if signal.size else 0.0


def _summary(x: np.ndarray, y: np.ndarray, sr: int, ratio: float) -> dict:
    """No gain compensation is applied; these are observed peaks and RMS."""
    input_peak, output_peak = _peak(x), _peak(y)
    input_4x = _peak(resample_poly(x, 4, 1, axis=0)) if len(x) else 0.0
    output_4x = _peak(resample_poly(y, 4, 1, axis=0)) if len(y) else 0.0
    return {
        "sample_rate": int(sr),
        "ratio": float(ratio),
        "input_samples": len(x),
        "output_samples": len(y),
        "target_samples": round(len(x) * ratio),
        "duration_error_samples": len(y) - round(len(x) * ratio),
        "input_sample_peak": input_peak,
        "output_sample_peak": output_peak,
        "input_4x_peak_estimate": input_4x,
        "output_4x_peak_estimate": output_4x,
        "sample_peak_gain": output_peak / input_peak if input_peak else None,
        "oversampled_peak_gain": output_4x / input_4x if input_4x else None,
        "input_rms": float(np.sqrt(np.mean(x * x))) if x.size else 0.0,
        "output_rms": float(np.sqrt(np.mean(y * y))) if y.size else 0.0,
        "finite": bool(np.all(np.isfinite(y))),
        "amplitude_normalization": False,
        "limiter_or_clipping": False,
        "peak_estimate_caveat": "4x polyphase estimate; not certified true peak",
    }


def _nearest_peak_regions(magnitude: np.ndarray) -> np.ndarray:
    """Nearest local maximum; this is bin grouping, not partial tracking."""
    peaks = np.flatnonzero(
        (magnitude[1:-1] > magnitude[:-2])
        & (magnitude[1:-1] >= magnitude[2:])
        & (magnitude[1:-1] >= np.max(magnitude) * 1e-4)
    ) + 1
    if not len(peaks):
        return np.arange(len(magnitude))
    bins = np.arange(len(magnitude))
    insertion = np.searchsorted(peaks, bins)
    left = peaks[np.maximum(insertion - 1, 0)]
    right = peaks[np.minimum(insertion, len(peaks) - 1)]
    return np.where(bins - left <= right - bins, left, right)


def stretch(
    x: np.ndarray,
    sr: int,
    ratio: float,
    protected: bool = True,
    *,
    identity_phase_locking: bool = True,
    transient_resets: bool = True,
) -> tuple[np.ndarray, dict]:
    """Expand mono/stereo duration at fixed pitch, returning audio and diagnostics.

    The required API is ``stretch(x[N,C], sr, ratio, protected=True)``. Ratios
    1.25 and 1.50 use N=2048/Ha=512/Hs=640 or 768. Ratio 1 is exact bypass.
    One-dimensional mono retains its shape; C must otherwise be one or two.
    Both controls share phase offsets across channels. ``protected=False``
    disables locking and resets, providing an elementary raw-PV control.
    """
    signal = np.asarray(x, dtype=np.float64)
    one_dimensional = signal.ndim == 1
    if one_dimensional:
        signal = signal[:, None]
    if signal.ndim != 2 or signal.shape[1] not in (1, 2):
        raise ValueError("x must have shape (samples, 1 or 2), or (samples,)")
    if not np.all(np.isfinite(signal)):
        raise ValueError("x must contain only finite samples")
    if not np.isscalar(sr) or not np.isfinite(sr) or sr <= 0 or int(sr) != sr:
        raise ValueError("sr must be a positive integer sample rate in Hz")
    ratio = float(ratio)
    if ratio not in (1.0, 1.25, 1.5):
        raise ValueError("research prototype supports ratios 1.0, 1.25 and 1.50")
    use_locking = bool(protected and identity_phase_locking)
    use_resets = bool(protected and transient_resets)
    diagnostics = {
        "algorithm": "established fixed-hop stereo-shared phase vocoder",
        "protected": bool(protected),
        "identity_phase_locking": use_locking,
        "transient_resets": use_resets,
        "frame_size": FRAME_SIZE,
        "analysis_hop": ANALYSIS_HOP,
        "synthesis_hop": round(ANALYSIS_HOP * ratio),
        "reference_policy": "dominant channel per bin; 0.85 continuity hysteresis",
        "transient_reset_frames": [],
        "transient_reset_input_times_seconds": [],
        "reference_switch_count": 0,
        "frame_count": 0,
        "synthesis_coefficient_ipd_error_rad": 0.0 if signal.shape[1] == 2 else None,
        "ipd_diagnostic_scope": "synthesis coefficients; independent output measurement required",
        "gate_status": "INCOMPLETE: transient and creator-listening evaluation required",
    }
    if ratio == 1.0 or not len(signal):
        result = signal.copy()
        diagnostics["exact_bypass"] = ratio == 1.0
        diagnostics.update(_summary(signal, result, sr, ratio))
        return (result[:, 0] if one_dimensional else result), diagnostics

    n_fft, ha, hs = FRAME_SIZE, ANALYSIS_HOP, diagnostics["synthesis_hop"]
    half = n_fft // 2
    last_center = ((len(signal) + ha - 1) // ha) * ha
    padded = np.pad(signal, ((half, half + last_center - len(signal)), (0, 0)))
    frame_count = last_center // ha + 1
    window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n_fft) / n_fft)
    omega = 2 * np.pi * np.arange(n_fft // 2 + 1) / n_fft
    bins = np.arange(len(omega))
    output = np.zeros(((frame_count - 1) * hs + n_fft, signal.shape[1]))
    denominator = np.zeros(len(output))
    common_offset = np.zeros_like(omega)
    previous_phase = np.zeros((len(omega), signal.shape[1]))
    previous_magnitude = np.zeros_like(omega)
    reference = np.zeros(len(omega), dtype=int)
    previous_rms = 0.0
    last_reset = -np.inf
    ipd_error_sum = ipd_weight_sum = 0.0
    unreliable_bins = 0
    minimum_dwell_frames = max(1, int(np.ceil(0.05 * sr / ha)))

    for frame_index in range(frame_count):
        analysis = padded[frame_index * ha : frame_index * ha + n_fft]
        spectrum = np.fft.rfft(analysis * window[:, None], axis=0)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)
        combined = np.sqrt(np.sum(magnitude * magnitude, axis=1))
        frame_max = float(np.max(combined))
        frame_rms = float(np.sqrt(np.mean(analysis * analysis)))
        reliable = combined >= max(MAGNITUDE_FLOOR, frame_max * 1e-6)
        unreliable_bins += int(np.sum(~reliable))
        strongest = np.argmax(magnitude, axis=1)
        keep = magnitude[bins, reference] >= 0.85 * magnitude[bins, strongest]
        new_reference = np.where(keep, reference, strongest)
        diagnostics["reference_switch_count"] += int(np.sum(new_reference != reference))
        reference = new_reference

        if frame_index:
            residual = _wrap(
                phase[bins, reference] - previous_phase[bins, reference] - omega * ha
            )
            instantaneous = omega + np.where(reliable, residual, 0.0) / ha
            common_offset = _wrap(common_offset + instantaneous * (hs - ha))

        flux = float(np.sum(np.maximum(0.0, combined - previous_magnitude)))
        normalized_flux = flux / max(float(np.sum(previous_magnitude)), MAGNITUDE_FLOOR)
        silent = frame_max <= MAGNITUDE_FLOOR
        onset = (
            not silent
            and normalized_flux >= 0.60
            and frame_rms >= max(previous_rms * 1.50, MAGNITUDE_FLOOR)
            and frame_index - last_reset >= minimum_dwell_frames
        )
        if silent:
            common_offset.fill(0.0)
        elif use_resets and onset:
            common_offset.fill(0.0)
            last_reset = frame_index
            diagnostics["transient_reset_frames"].append(frame_index)
            diagnostics["transient_reset_input_times_seconds"].append(frame_index * ha / sr)

        synthesis_offset = common_offset
        if use_locking and not silent:
            synthesis_offset = common_offset[_nearest_peak_regions(combined)]
        modified = magnitude * np.exp(1j * (phase + synthesis_offset[:, None]))
        if signal.shape[1] == 2:
            # Ignore real-only DC/Nyquist and unreliable stereo coefficients.
            stereo_reliable = reliable & np.all(magnitude >= frame_max * 1e-4, axis=1)
            stereo_reliable[[0, -1]] = False
            weight = np.sqrt(magnitude[:, 0] * magnitude[:, 1]) * stereo_reliable
            error = np.abs(_wrap(np.angle(modified[:, 0] * np.conj(modified[:, 1]))
                                 - np.angle(spectrum[:, 0] * np.conj(spectrum[:, 1]))))
            ipd_error_sum += float(np.sum(weight * error))
            ipd_weight_sum += float(np.sum(weight))
        reconstructed = np.fft.irfft(modified, n=n_fft, axis=0)
        start = frame_index * hs
        output[start : start + n_fft] += reconstructed * window[:, None]
        denominator[start : start + n_fft] += window * window
        previous_phase, previous_magnitude, previous_rms = phase, combined, frame_rms

    target_samples = round(len(signal) * ratio)
    interval = slice(half, half + target_samples)
    retained_denominator = denominator[interval]
    if len(retained_denominator) != target_samples or np.any(retained_denominator <= 1e-12):
        raise RuntimeError("unsafe overlap-add normalization on retained interval")
    result = output[interval] / retained_denominator[:, None]
    if not np.all(np.isfinite(result)):
        raise RuntimeError("nonfinite phase-vocoder reconstruction")
    diagnostics.update({
        "exact_bypass": False,
        "frame_count": frame_count,
        "padding_samples_each_initial_side": half,
        "tail_alignment_padding_samples": last_center - len(signal),
        "minimum_retained_window_square_sum": float(np.min(retained_denominator)),
        "unreliable_bin_fraction": unreliable_bins / (frame_count * len(omega)),
        "transient_reset_count": len(diagnostics["transient_reset_frames"]),
    })
    if signal.shape[1] == 2:
        diagnostics["synthesis_coefficient_ipd_error_rad"] = (
            ipd_error_sum / ipd_weight_sum if ipd_weight_sum else 0.0
        )
    diagnostics.update(_summary(signal, result, sr, ratio))
    return (result[:, 0] if one_dimensional else result), diagnostics
