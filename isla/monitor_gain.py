"""Optional post-DSP attenuation for the ISLA graphical LIVE listening output.

This adapter is intentionally outside the Experiment 02 frozen LIVE engine.
It wraps the existing streaming processor and preserves exact unity output,
original DSP state, callback behavior, device routing and recovery semantics.
"""
from __future__ import annotations

import numpy as np

from isla.streaming import StreamingDSP


class MonitorVolume:
    """GUI session setting: 0% mute, 100% unity, never amplifies."""
    def __init__(self):
        self.percent = 100

    def set_percent(self, value):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError("LIVE listening volume must be an integer from 0 to 100%.")
        self.percent = value


class ListeningGainDSP:
    """Apply a bounded 5 ms attenuation ramp after the unchanged LIVE DSP."""

    def __init__(self, rate, channels, volume: MonitorVolume, *, delegate_factory=StreamingDSP):
        self.delegate = delegate_factory(rate, channels)
        self.volume = volume
        self.rate = rate
        self._applied = volume.percent / 100.0

    @property
    def delay(self):
        return self.delegate.delay

    @property
    def mode(self):
        return self.delegate.mode

    def select(self, mode):
        return self.delegate.select(mode)

    def process_block(self, block):
        result = self.delegate.process_block(block)
        target, previous = self.volume.percent / 100.0, self._applied
        if target != previous:
            n = min(len(result), max(2, round(self.rate * .005)))
            ramp = np.linspace(previous, target, n, dtype=np.float32)[:, None]
            np.multiply(result[:n], ramp, out=result[:n])
            if n < len(result) and target != 1.0:
                result[n:] *= target
            self._applied = target
        elif target != 1.0:
            result *= target
        # At 100% stable gain this returns the unmodified delegate output.
        return result
