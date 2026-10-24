"""
HarmonicBlender
---------------
Final stage of the Phased-Music-Notes DSP pipeline.

Responsibilities:
    - Smooth harmonic content after phase-aligned transitions
    - Reduce harsh overtones introduced by boundary blending
    - Apply spectral softening (mode-dependent)
    - Preserve timbre while reducing transient spikes

Techniques:
    - Short-time FFT
    - Harmonic envelope smoothing
    - Spectral tilt
    - Soft lowpass blending

This module is intentionally simple and deterministic so Jules
can extend it with more advanced DSP later.
"""

from __future__ import annotations
import numpy as np
from typing import Optional


class HarmonicBlender:
    """
    Harmonic blending engine.

    Parameters
    ----------
    strength : float
        Amount of harmonic smoothing (0.0 - 1.0).
    window_ms : int
        FFT window size in milliseconds.
    """

    def __init__(self,
                 strength: float = 0.4,
                 window_ms: int = 40):

        self.strength = float(np.clip(strength, 0.0, 1.0))
        self.window_ms = window_ms

    # -------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------
    def blend(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Apply harmonic blending to mono or stereo audio.

        Parameters
        ----------
        audio : np.ndarray
            Mono or stereo audio buffer.
        sr : int
            Sample rate.

        Returns
        -------
        np.ndarray
            Harmonic-blended audio buffer.
        """

        audio = np.asarray(audio)
        if sr <= 0:
            raise ValueError("Sample rate must be positive.")
        if audio.ndim not in (1, 2):
            raise ValueError("Audio must be mono or stereo.")
        if audio.shape[0] == 0:
            return audio.copy()

        if audio.ndim == 1:
            return self._blend_mono(audio, sr)
        elif audio.ndim == 2:
            return self._blend_stereo(audio, sr)

    # -------------------------------------------------------------
    # Mono processing
    # -------------------------------------------------------------
    def _blend_mono(self, audio: np.ndarray, sr: int) -> np.ndarray:
        win = self._hann_window(sr)
        win_samples = win.size
        if win_samples < 2:
            raise ValueError("window_ms is too small for the sample rate.")
        hop = max(1, win_samples // 2)

        # Pad for WOLA
        pad_front = win_samples - hop
        pad_back = win_samples
        audio_padded = np.pad(audio, (pad_front, pad_back), mode='constant')

        # STFT
        frames = self._frame_audio(audio_padded, hop, win_samples)
        spectrum = np.fft.rfft(frames * win, axis=1)
        mag = np.abs(spectrum)
        phase = np.angle(spectrum)

        # Harmonic smoothing
        mag_smooth = self._smooth_harmonics(mag)

        # Reconstruct spectrum
        spectrum_blended = mag_smooth * np.exp(1j * phase)

        # ISTFT (WOLA applies synthesis window)
        frames_out = np.fft.irfft(spectrum_blended, axis=1)
        frames_out *= win
        audio_out = self._overlap_add(frames_out, hop)

        # Normalize envelope (sum of squares of window for WOLA)
        out_len = len(audio_out)
        envelope = np.zeros(out_len, dtype=np.float32)
        win_sq = win**2
        for i in range(len(frames_out)):
            start = i * hop
            envelope[start:start + win_samples] += win_sq

        envelope[envelope < 1e-7] = 1.0
        audio_out = audio_out / envelope

        # Strip the padding
        audio_out = audio_out[pad_front:pad_front + len(audio)]

        # Pad or truncate to match original length exactly
        if len(audio_out) < len(audio):
            pad_len = len(audio) - len(audio_out)
            audio_out = np.pad(audio_out, (0, pad_len))
        return audio_out[: len(audio)]

    # -------------------------------------------------------------
    # Stereo processing
    # -------------------------------------------------------------
    def _blend_stereo(self, audio: np.ndarray, sr: int) -> np.ndarray:
        out = np.zeros(audio.shape, dtype=np.result_type(audio.dtype, np.float32))
        for ch in range(audio.shape[1]):
            out[:, ch] = self._blend_mono(audio[:, ch], sr)
        return out

    # -------------------------------------------------------------
    # Harmonic smoothing core
    # -------------------------------------------------------------
    def _smooth_harmonics(self, mag: np.ndarray) -> np.ndarray:
        """
        Smooth harmonic magnitudes across frequency bins.

        This reduces harsh overtones and creates a soft timbre.
        """

        # Simple spectral smoothing kernel
        kernel = np.array([0.25, 0.5, 0.25])
        mag_smooth = np.copy(mag)

        for i in range(mag.shape[0]):
            mag_smooth[i] = np.convolve(mag[i], kernel, mode="same")

        # Apply strength
        return (1 - self.strength) * mag + self.strength * mag_smooth

    # -------------------------------------------------------------
    # Framing utilities
    # -------------------------------------------------------------
    @staticmethod
    def _frame_audio(audio: np.ndarray, hop: int, win: int) -> np.ndarray:
        remaining = max(0, len(audio) - win)
        num_frames = 1 + (remaining + hop - 1) // hop
        frames = np.zeros((num_frames, win), dtype=np.float32)

        for i in range(num_frames):
            start = i * hop
            end = start + win
            chunk = audio[start:end]
            frames[i, :len(chunk)] = chunk

        return frames

    @staticmethod
    def _overlap_add(frames: np.ndarray, hop: int) -> np.ndarray:
        win = frames.shape[1]
        out_len = hop * (frames.shape[0] - 1) + win
        out = np.zeros(out_len, dtype=np.float32)

        for i, frame in enumerate(frames):
            start = i * hop
            out[start:start + win] += frame

        return out

    # -------------------------------------------------------------
    # Window generator
    # -------------------------------------------------------------
    def _hann_window(self, sr: int) -> np.ndarray:
        win_samples = self._ms_to_samples(self.window_ms, sr)
        # Use periodic Hann window which sums to exactly 1.0 when overlapped by 50%
        n = np.arange(win_samples)
        return 0.5 - 0.5 * np.cos(2 * np.pi * n / win_samples)

    # -------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------
    @staticmethod
    def _ms_to_samples(ms: float, sr: int) -> int:
        return int((ms / 1000.0) * sr)
