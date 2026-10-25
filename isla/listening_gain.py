"""Preallocated, bounded output-only gain ramp; no audio buffer is modified upstream."""
from __future__ import annotations

import numpy as np


class GainRamp:
    """Five millisecond linear transitions across arbitrarily sized output blocks.

    Allocate workspace before streaming. The consumer alone owns ramp state;
    command threads publish only a scalar target through their settings object.
    """
    def __init__(self, rate, percent, capacity=512):
        self.applied = percent / 100.0
        self.target = self.applied
        self.length = max(2, round(rate * .005))
        self.remaining = 0
        self.step = 0.0
        self.steps = np.arange(1, capacity + 1, dtype=np.float32)
        self.scratch = np.empty(capacity, dtype=np.float32)

    def apply(self, output, percent):
        target = percent / 100.0
        if target != self.target:
            self.target = target
            self.remaining = self.length
            self.step = (target - self.applied) / self.length
        offset = 0
        while self.remaining and offset < len(output):
            count = min(self.remaining, len(output) - offset, len(self.scratch))
            ramp = self.scratch[:count]
            np.multiply(self.steps[:count], self.step, out=ramp)
            np.add(ramp, self.applied, out=ramp)
            np.maximum(ramp, 0.0, out=ramp)
            np.minimum(ramp, 1.0, out=ramp)
            if count == self.remaining:
                ramp[-1] = self.target
            np.multiply(output[offset:offset+count], ramp[:, None],
                        out=output[offset:offset+count])
            self.applied += count * self.step
            self.remaining -= count
            offset += count
            if not self.remaining:
                self.applied = self.target
        if offset < len(output) and self.applied != 1.0:
            np.multiply(output[offset:], self.applied, out=output[offset:])
