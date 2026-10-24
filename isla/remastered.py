"""Opt-in, offline Experiment 02 adapter. The frozen renderer is never edited.

Percent controls permitted depth, not level, wet/dry mix or perceived intensity.
Only the selected depth changes; recovery uses that same immutable Config field.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from numbers import Integral
from types import MappingProxyType

import numpy as np
from scipy.signal import resample_poly

BASELINE_DEPTHS = MappingProxyType({"velvet": .16, "legato": .30, "melt": .30})
CORE_SHA256 = "91a673b9c894d4af768ae966177d0f38c3f17d8e2b9e898e82e2082e083158a0"
PEAK_CEILING = .98  # Research admission screen, not a limiter or true-peak claim.


@dataclass(frozen=True)
class RenderRequest:
    mode: str
    intensity: int = 100

    def __post_init__(self):
        if self.mode not in BASELINE_DEPTHS:
            raise ValueError("Remastered mode must be velvet, legato or melt.")
        if (isinstance(self.intensity, bool) or not isinstance(self.intensity, Integral)
                or not 0 <= self.intensity <= 100 or self.intensity % 5):
            raise ValueError("Remastered intensity must be 0–100 in 5% increments.")

    @property
    def depth(self):
        return BASELINE_DEPTHS[self.mode] * (self.intensity / 100)

    def configuration(self):
        # Lazy import: ordinary production playback has no research dependency.
        from tools.resonance02.core import Config
        return replace(Config(), **{self.mode + "_depth": self.depth})


def signal_metrics(x):
    values = np.asarray(x, dtype=np.float64)
    return {
        "sample_peak": float(np.max(np.abs(values), initial=0.)),
        "rms": float(np.sqrt(np.mean(values * values))),
        "four_x_peak_estimate": float(np.max(np.abs(
            resample_poly(values, 4, 1, axis=0)), initial=0.)),
    }


def output_metrics(x, y):
    result = signal_metrics(y)
    difference = np.asarray(y, dtype=np.float64) - np.asarray(x, dtype=np.float64)
    residual = float(np.sqrt(np.mean(difference * difference)))
    input_rms = float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))
    result.update(residual_rms=residual,
                  residual_relative_rms=residual / input_rms if input_rms else 0.,
                  max_sample_difference=float(np.max(np.abs(difference), initial=0.)),
                  finite=bool(np.isfinite(y).all()),
                  shape_preserved=y.shape == x.shape,
                  exact_copy=y.dtype == x.dtype and y.tobytes() == x.tobytes())
    result["peak_screen_pass"] = (result["sample_peak"] <= PEAK_CEILING and
                                  result["four_x_peak_estimate"] <= PEAK_CEILING)
    return result


def render_preview(x, sr, request: RenderRequest):
    """Return raw research samples and measured diagnostics, outside callbacks.

    100% is bit-identical to core.render on the same input/dtype/environment.
    0% takes core.render's exact-copy path, without FFT reconstruction. Analysis
    still runs so the veto and control evidence remains available even at zero.
    A separate preparation worker casts to PortAudio float32 and screens it.
    """
    from pathlib import Path
    from tools.resonance02 import core

    if hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest() != CORE_SHA256:
        raise ValueError("Experiment 02 core differs from the frozen research authority.")
    x = core.validate(x, sr)
    if not len(x) or x.dtype not in (np.dtype('float32'), np.dtype('float64')):
        raise ValueError("Remastered needs non-empty float32/float64 audio.")
    cfg = request.configuration()
    analysis = core.analyze(x, sr, cfg)
    y, diagnostic = core.render(x, sr, request.mode, 'governed', cfg, analysis)
    f = analysis['features']
    attacks, uncertain, quiet = f[:, 6] >= .5, f[:, 5] < .2, f[:, 8] != 0
    veto = attacks | uncertain | quiet
    u, target = diagnostic['control'], diagnostic['target']
    allowance = request.depth * (cfg.hop / sr) / cfg.recovery_s
    checks = {
        "control_bounded": bool(np.all((u >= 0) & (u <= request.depth))),
        "veto_zero": bool(np.all(u[veto] == 0)),
        "recovery_bounded": bool(np.all(
            np.abs(np.diff(u, prepend=0.))[~veto] <= allowance + 1e-14)),
        "spectral_gain_bounded": (diagnostic['gain_min'] >= cfg.gain_min and
                                   diagnostic['gain_max'] <= cfg.gain_max),
        "phase_bounded": diagnostic['phase_max'] <= cfg.phase_max_rad,
        "state_weights_normalized": bool(np.allclose(
            analysis['states'].sum(axis=1), 1., rtol=0, atol=1e-14)),
    }
    report = {
        "schema": 1, "preview": "v4.0 Remastered / Experiment 02 governed",
        "scientific_verdict": "REVISE / INCONCLUSIVE; no production promotion",
        "research_core_sha256": CORE_SHA256,
        "source_audio_sha256": hashlib.sha256(x.tobytes()).hexdigest(),
        "source_dtype": str(x.dtype), "sample_rate": int(sr), "channels": x.shape[1],
        "samples": len(x), "mode": request.mode, "intensity_percent": int(request.intensity),
        "baseline_depth": BASELINE_DEPTHS[request.mode], "requested_depth": request.depth,
        "target_depth_mean": float(np.mean(target)),
        "target_depth_max": float(np.max(target, initial=0.)),
        "applied_depth_active_mean": diagnostic['effective_depth'],
        "applied_depth_max": float(np.max(u, initial=0.)),
        "frame_count": len(u), "vetoed_frames": int(np.count_nonzero(veto)),
        "attack_veto_frames": int(np.count_nonzero(attacks)),
        "confidence_veto_frames": int(np.count_nonzero(uncertain)),
        "silence_veto_frames": int(np.count_nonzero(quiet)),
        "recovery_allowance_per_hop": allowance,
        "rate_limit_frames": diagnostic['rate_limit_frames'],
        "gain_limit_frames": diagnostic['gain_limit_frames'],
        "spectral_gain_min": diagnostic['gain_min'],
        "spectral_gain_max": diagnostic['gain_max'], "phase_max_rad": diagnostic['phase_max'],
        "input": signal_metrics(x), "raw_output": output_metrics(x, y), "checks": checks,
    }
    report['numerical_pass'] = bool(all(checks.values()) and
        report['raw_output']['finite'] and report['raw_output']['shape_preserved'] and
        report['raw_output']['peak_screen_pass'])
    return y, report
