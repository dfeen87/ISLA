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
        if win.size < 2:
            raise ValueError("window_ms is too small for the sample rate.")
        hop = max(1, win.size // 2)

        # To avoid edge artifacts and properly reconstruct the beginning of the signal,
        # we pad the start with zeros. We pad the end to cover the last frame.
        pad_front = win.size - hop
        # Calculate padding needed to cover the last frame
        num_samples = len(audio)
        num_frames = int(np.ceil((num_samples + pad_front) / hop))
        pad_back = num_frames * hop + win.size - hop - num_samples - pad_front

        padded_audio = np.pad(audio, (pad_front, pad_back), mode='constant')

        # STFT
        frames = self._frame_audio(padded_audio, hop, win.size)
        spectrum = np.fft.rfft(frames * win, axis=1)
        mag = np.abs(spectrum)
        phase = np.angle(spectrum)

        # Harmonic smoothing
        mag_smooth = self._smooth_harmonics(mag)

        # Reconstruct spectrum
        spectrum_blended = mag_smooth * np.exp(1j * phase)

        # ISTFT
        # We need to multiply by the window again in the synthesis stage for
        # proper overlap-add reconstruction with a Hann window
        # Explicitly pass n=win.size to handle odd-length windows correctly.
        frames_out = np.fft.irfft(spectrum_blended, n=win.size, axis=1) * win

        # Calculate weights for normalization
        win_sq = win ** 2
        weights_frames = np.tile(win_sq, (frames_out.shape[0], 1))

        out_padded, weights_padded = self._overlap_add_with_weights(frames_out, weights_frames, hop)

        # Normalization to avoid dividing by 0
        eps = 1e-8
        audio_out_padded = out_padded / (weights_padded + eps)

        # Strip the padding we added at the front and crop to original length
        audio_out = audio_out_padded[pad_front : pad_front + len(audio)]
        return audio_out

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

    @staticmethod
    def _overlap_add_with_weights(frames: np.ndarray, weights_frames: np.ndarray, hop: int) -> tuple[np.ndarray, np.ndarray]:
        win = frames.shape[1]
        out_len = hop * (frames.shape[0] - 1) + win
        out = np.zeros(out_len, dtype=np.float32)
        weights_out = np.zeros(out_len, dtype=np.float32)

        for i, (frame, w_frame) in enumerate(zip(frames, weights_frames)):
            start = i * hop
            out[start:start + win] += frame
            weights_out[start:start + win] += w_frame

        return out, weights_out

    # -------------------------------------------------------------
    # Window generator
    # -------------------------------------------------------------
    def _hann_window(self, sr: int) -> np.ndarray:
        win_samples = self._ms_to_samples(self.window_ms, sr)
        return np.hanning(win_samples)

    # -------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------
    @staticmethod
    def _ms_to_samples(ms: float, sr: int) -> int:
        return int((ms / 1000.0) * sr)
