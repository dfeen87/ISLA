"""Stateful LIVE harmonic profiles; offline BEDROCK remains unchanged.

Fixed 2048-sample windows / 512-sample hops retain analysis history and
weighted overlap-add tails across *every* transport block. All profiles stay
warm, including during bypass. No per-chunk padding or note detection.
"""
from __future__ import annotations

import numpy as np

from isla.harmonics import HarmonicBlender

MODES = ("bypass", "velvet", "legato", "melt")


class StreamingDSP:
    hop = 512
    window_size = 2048
    delay = window_size - hop

    def __init__(self, samplerate, channels):
        if samplerate not in (44100, 48000) or channels not in (1, 2):
            raise ValueError("LIVE supports 44100/48000 Hz and mono/stereo only.")
        self.sr, self.channels = samplerate, channels
        self.mode = "bypass"
        self.window = (.5 - .5 * np.cos(2 * np.pi * np.arange(self.window_size) / self.window_size))[:, None]
        self.history = np.zeros((self.window_size, channels))
        self.tails = np.zeros((3, self.window_size, channels))
        self.weights = np.zeros((self.window_size, 1))
        self.dry = np.zeros((self.delay, channels), np.float32)
        # Reuse BEDROCK's spectral kernel without its offline framing/padding.
        # LIVE profiles deliberately omit offline note-boundary interpolation.
        self.blenders = [HarmonicBlender(strength=s) for s in (.35, .55, .75)]
        self.mix = np.array([1., 0., 0., 0.])
        n = round(.005 * samplerate)
        self.fade = np.minimum(1., (np.arange(self.hop) + 1) / n)[:, None]

    def select(self, mode):
        if mode not in MODES:
            raise ValueError("Choose bypass, velvet, legato, or melt.")
        self.mode = mode  # Published reference, consumed by the worker at hop edge.

    def process_block(self, block):
        block = np.asarray(block, dtype=np.float32)
        if block.shape != (self.hop, self.channels):
            raise ValueError("StreamingDSP requires one 512-frame mono/stereo hop.")
        # Contaminated blocks are muted as a whole; never poison retained state.
        if not np.isfinite(block).all():
            block = np.zeros_like(block)
        self.history[:-self.hop] = self.history[self.hop:]
        self.history[-self.hop:] = block
        spectrum = np.fft.rfft(self.history * self.window, axis=0)
        magnitude = np.abs(spectrum)
        phase = np.exp(1j * np.angle(spectrum))
        self.weights += self.window ** 2
        for tail, blender in zip(self.tails, self.blenders):
            smooth = blender._smooth_harmonics(magnitude.T).T
            tail += np.fft.irfft(smooth * phase, n=self.window_size, axis=0) * self.window
        wet = self.tails[:, :self.hop] / np.maximum(self.weights[:self.hop], 1e-8)
        dry = self.dry[:self.hop].copy()
        self.dry[:-self.hop] = self.dry[self.hop:]
        self.dry[-self.hop:] = block
        banks = np.concatenate((dry[None], wet), axis=0)
        target = np.zeros(4)
        target[MODES.index(self.mode)] = 1
        mix = self.mix[None] + self.fade * (target - self.mix)[None]
        result = np.einsum("hmc,mh->hc", banks.transpose(1, 0, 2), mix.T)
        self.mix = target
        self.tails[:, :-self.hop] = self.tails[:, self.hop:]
        self.tails[:, -self.hop:] = 0
        self.weights[:-self.hop] = self.weights[self.hop:]
        self.weights[-self.hop:] = 0
        # No normalization or clipping: bypass preserves finite float32 exactly.
        return result.astype(np.float32)
