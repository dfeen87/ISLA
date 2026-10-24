"""Opt-in adapters around the unmodified v3.1.0 LIVE transport and kernel.

No production default, offline algorithm, timing, or reconstruction is edited.
Each adapter changes one bank only. Amount zero delegates bit-for-bit.
"""
from __future__ import annotations

import numpy as np

from isla.streaming import StreamingDSP

SWEEPS = {"velvet": (.10, .20, .30), "legato": (.25, .50, .75),
          "melt": (.15, .30, .45)}
SHOWCASE = {name: values[1] for name, values in SWEEPS.items()}


class EnvelopeAdapter:
    def __init__(self, original, profile, amount, samplerate):
        self.original, self.profile, self.amount = original, profile, float(amount)
        self.previous = np.zeros(1025)
        self.memory = np.ones(1025)
        frequency = np.fft.rfftfreq(2048, 1 / samplerate)
        self.frequency_weight = frequency ** 2 / (frequency ** 2 + 3000. ** 2)
        self.last_gate = 0.
        self.last_gain_min = self.last_gain_max = 1.
        self.last_energy_ratio = 1.

    def _smooth_harmonics(self, magnitude):
        baseline = self.original._smooth_harmonics(magnitude)
        if self.amount == 0:
            return baseline
        # A common control from both channels; no audio is mixed across them.
        pooled = np.sqrt(np.mean(magnitude ** 2, axis=0))
        shaped = np.sqrt(np.mean(baseline ** 2, axis=0))
        total, previous_total = pooled.sum(), self.previous.sum()
        if total == 0:
            self.previous.fill(0)
            self.memory.fill(1)
            self.last_gate = 0.
            self.last_gain_min = self.last_gain_max = 1.
            self.last_energy_ratio = 1.
            return baseline
        flux = np.maximum(pooled - self.previous, 0).sum() / total
        # Fixed safeguards in all sweeps. Strong novelty and fast decay reset
        # to the original bank; these are spectral heuristics, not note labels.
        rising = np.clip((.30 - flux) / .22, 0., 1.)
        falling = (np.clip((total / previous_total - .50) / .35, 0., 1.)
                   if previous_total else 0.)
        gate = float(rising * falling)
        self.previous[:] = pooled
        tiny = np.finfo(np.float64).tiny
        if self.profile == "legato":
            current = np.clip(shaped / np.maximum(pooled, tiny), .75, 1.25)
            alpha = self.amount * gate
            self.memory[:] = (1 - alpha) * current + alpha * self.memory
            gain = np.clip(self.memory / current, .8, 1.2)
        else:
            kernel = ([.25, .5, .25] if self.profile == "velvet"
                      else [1/16, 4/16, 6/16, 4/16, 1/16])
            envelope = np.convolve(shaped, kernel, mode="same")
            curvature = np.clip((envelope - shaped) / np.maximum(shaped, tiny), -1., 1.)
            weight = self.frequency_weight if self.profile == "velvet" else 1.
            gain = 1 + self.amount * gate * weight * curvature
        candidate = baseline * gain[None, :]
        # Attenuation-only common energy cap: never normalize upward. This
        # bounds frame energy, not arbitrary WOLA sample or intersample peaks.
        before, after = np.sum(baseline ** 2), np.sum(candidate ** 2)
        cap = min(1., float(np.sqrt(before / after))) if after else 1.
        candidate *= cap
        self.last_gate = gate
        self.last_gain_min = float(np.min(gain) * cap)
        self.last_gain_max = float(np.max(gain) * cap)
        self.last_energy_ratio = float(np.sum(candidate ** 2) / before) if before else 1.
        return candidate


class IdentityDSP(StreamingDSP):
    """Supply {profile: amount}; omitted profiles remain exactly original."""
    def __init__(self, samplerate, channels, amounts=None):
        super().__init__(samplerate, channels)
        amounts = dict(amounts or {})
        for profile, amount in amounts.items():
            if profile not in SWEEPS or not np.isfinite(amount) or not 0 <= amount <= max(SWEEPS[profile]):
                raise ValueError("Unknown profile or out-of-range research amount")
        self.blenders = [EnvelopeAdapter(original, profile, amounts.get(profile, 0), samplerate)
                         for profile, original in zip(SWEEPS, self.blenders)]


def render(audio, rate, mode, amounts=None, schedule=None):
    """Full emissions plus delay-aligned passage; zero-pad a partial last hop."""
    dsp = IdentityDSP(rate, audio.shape[1], amounts)
    length = ((len(audio) + 2 * dsp.delay + 511) // 512) * 512
    padded = np.pad(audio, ((0, length - len(audio)), (0, 0)))
    raw = []
    for index, block in enumerate(padded.reshape(-1, 512, audio.shape[1])):
        dsp.select(schedule[index % len(schedule)] if schedule else mode)
        raw.append(dsp.process_block(block))
    raw = np.concatenate(raw)
    return raw[dsp.delay:dsp.delay + len(audio)], raw
