"""Post-freeze successor 01: isolated-transient timing, offline research only.

The frozen engine and experiment replay remain in slowdown.py and run.py.
See SLOWDOWN_SUCCESSOR.md for the separately registered mechanism and limits.
"""
from __future__ import annotations

import numpy as np

from . import slowdown as frozen


def _anchors(signal: np.ndarray, reset_frames: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Refine the unchanged detector; never use externally supplied event times."""
    energy = np.sum(signal * signal, axis=1)
    rise = np.maximum(0.0, np.diff(energy, prepend=0.0))
    half = frozen.FRAME_SIZE // 2
    found = []
    for frame in reset_frames:
        center = frame * frozen.ANALYSIS_HOP
        lo, hi = max(0, center - half), min(len(signal), center + half)
        if hi > lo and np.max(rise[lo:hi]) > 0:
            found.append(lo + int(np.argmax(rise[lo:hi])))
    anchors = np.unique(found).astype(int)
    if not len(anchors):
        return anchors, anchors.copy()
    gaps = np.diff(anchors)
    isolated = np.minimum(np.r_[np.inf, gaps], np.r_[gaps, np.inf]) >= 2 * frozen.FRAME_SIZE
    return anchors[isolated], anchors[~isolated]


def _schedule(centers: np.ndarray, anchors: np.ndarray, ratio: float) -> tuple[np.ndarray, np.ndarray]:
    """Translate whole transient windows; interpolate only the intervening time."""
    half = frozen.FRAME_SIZE // 2
    knots = {0: 0.0, int(centers[-1]): float(centers[-1] * ratio)}
    protected = np.zeros(len(centers), dtype=bool)
    for anchor in anchors:
        delay = round(int(anchor) * ratio) - int(anchor)
        left, right = max(0, int(anchor) - half), min(int(centers[-1]), int(anchor) + half)
        knots[left], knots[right] = float(left + delay), float(right + delay)
        protected |= abs(centers - anchor) <= half
    positions = sorted(knots)
    synthesis = np.rint(np.interp(centers, positions, [knots[p] for p in positions])).astype(int)
    if np.any(np.diff(synthesis) <= 0) or np.any(np.diff(synthesis) >= frozen.FRAME_SIZE):
        raise RuntimeError("unsafe successor synthesis schedule")
    return synthesis, protected


def stretch(x, sr, ratio, protected=True, *, identity_phase_locking=True, transient_resets=True):
    """Same research API and screens; explicit successor, no production caller."""
    baseline, diagnostic = frozen.stretch(x, sr, ratio, protected,
        identity_phase_locking=identity_phase_locking, transient_resets=transient_resets)
    ratio = float(ratio)
    diagnostic = dict(diagnostic, successor="post-freeze-01", successor_applied=False,
                      transient_anchor_samples=[], unsupported_dense_anchor_samples=[])
    if ratio == 1 or not len(baseline) or not (protected and transient_resets):
        return baseline, diagnostic
    signal = np.asarray(x, dtype=np.float64)
    mono = signal.ndim == 1
    if mono:
        signal = signal[:, None]
    anchors, rejected = _anchors(signal, diagnostic["transient_reset_frames"])
    diagnostic["transient_anchor_samples"] = anchors.tolist()
    diagnostic["unsupported_dense_anchor_samples"] = rejected.tolist()
    if not len(anchors):
        return baseline, diagnostic

    n_fft, ha = frozen.FRAME_SIZE, frozen.ANALYSIS_HOP
    half = n_fft // 2
    last_center = ((len(signal) + ha - 1) // ha) * ha
    centers = np.arange(0, last_center + 1, ha)
    synthesis, analysis_phase = _schedule(centers, anchors, ratio)
    padded = np.pad(signal, ((half, half + last_center - len(signal)), (0, 0)))
    window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n_fft) / n_fft)
    omega = 2 * np.pi * np.arange(n_fft // 2 + 1) / n_fft
    bins = np.arange(len(omega))
    output = np.zeros((int(synthesis[-1]) + n_fft, signal.shape[1]))
    denominator = np.zeros(len(output))
    offset = np.zeros_like(omega)
    previous_phase = np.zeros((len(omega), signal.shape[1]))
    reference = np.zeros(len(omega), dtype=int)
    resets = set(diagnostic["transient_reset_frames"])
    ipd_error_sum = ipd_weight_sum = 0.0
    switches = 0
    for i, center in enumerate(centers):
        analysis = padded[center:center + n_fft]
        spectrum = np.fft.rfft(analysis * window[:, None], axis=0)
        magnitude, phase = np.abs(spectrum), np.angle(spectrum)
        combined = np.sqrt(np.sum(magnitude * magnitude, axis=1))
        frame_max = float(np.max(combined))
        reliable = combined >= max(frozen.MAGNITUDE_FLOOR, frame_max * 1e-6)
        strongest = np.argmax(magnitude, axis=1)
        keep = magnitude[bins, reference] >= 0.85 * magnitude[bins, strongest]
        new_reference = np.where(keep, reference, strongest)
        switches += int(np.sum(new_reference != reference))
        reference = new_reference
        if i:
            residual = frozen._wrap(phase[bins, reference] - previous_phase[bins, reference] - omega * ha)
            instantaneous = omega + np.where(reliable, residual, 0.0) / ha
            increment = int(synthesis[i] - synthesis[i - 1])
            offset = frozen._wrap(offset + instantaneous * (increment - ha))
        silent = frame_max <= frozen.MAGNITUDE_FLOOR
        if silent or analysis_phase[i] or i in resets:
            offset.fill(0.0)
        synthesis_offset = offset
        if identity_phase_locking and not silent:
            synthesis_offset = offset[frozen._nearest_peak_regions(combined)]
        modified = magnitude * np.exp(1j * (phase + synthesis_offset[:, None]))
        if signal.shape[1] == 2:
            mask = reliable & np.all(magnitude >= frame_max * 1e-4, axis=1)
            mask[[0, -1]] = False
            weight = np.sqrt(magnitude[:, 0] * magnitude[:, 1]) * mask
            error = np.abs(frozen._wrap(np.angle(modified[:, 0] * np.conj(modified[:, 1]))
                            - np.angle(spectrum[:, 0] * np.conj(spectrum[:, 1]))))
            ipd_error_sum += float(np.sum(weight * error))
            ipd_weight_sum += float(np.sum(weight))
        reconstructed = np.fft.irfft(modified, n=n_fft, axis=0)
        start = int(synthesis[i])
        output[start:start + n_fft] += reconstructed * window[:, None]
        denominator[start:start + n_fft] += window * window
        previous_phase = phase
    target = round(len(signal) * ratio)
    retained = denominator[half:half + target]
    if len(retained) != target or np.any(retained <= 1e-12):
        raise RuntimeError("unsafe successor overlap-add normalization")
    result = output[half:half + target] / retained[:, None]
    if not np.all(np.isfinite(result)):
        raise RuntimeError("nonfinite successor reconstruction")
    diagnostic.update(frozen._summary(signal, result, sr, ratio))
    diagnostic.update(algorithm="post-freeze-01 isolated-transient nonuniform phase vocoder",
        successor_applied=True, synthesis_hop=None,
        synthesis_centers_samples=synthesis.tolist(), analysis_phase_frames=np.flatnonzero(analysis_phase).tolist(),
        synthesis_hop_min=int(np.min(np.diff(synthesis))), synthesis_hop_max=int(np.max(np.diff(synthesis))),
        minimum_retained_window_square_sum=float(np.min(retained)), reference_switch_count=switches,
        gate_status="DEVELOPMENT ONLY: dense transients, recorded piano and listening unvalidated")
    # Frozen-pass bin reliability is not a reconstruction statistic for this pass.
    diagnostic.pop("unreliable_bin_fraction", None)
    if signal.shape[1] == 2:
        diagnostic["synthesis_coefficient_ipd_error_rad"] = ipd_error_sum / ipd_weight_sum if ipd_weight_sum else 0.0
    return (result[:, 0] if mono else result), diagnostic
