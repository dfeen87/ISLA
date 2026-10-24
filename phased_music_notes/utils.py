"""
utils.py
--------
Shared audio DSP utilities for ISLA (legacy module path).

This module provides:
    - window generators
    - normalization helpers
    - safe stereo/mono conversion
    - interpolation curves
    - framing utilities
    - smoothing kernels

These utilities keep the DSP modules clean and deterministic.
"""

from __future__ import annotations
import numpy as np


# -------------------------------------------------------------
# Audio normalization
# -------------------------------------------------------------
def normalize(audio: np.ndarray) -> np.ndarray:
    """
    Normalize audio to -1..1 range without clipping.
    """
    if audio.size == 0:
        return audio.copy()
    peak = np.max(np.abs(audio)) + 1e-9
    return audio / peak


# -------------------------------------------------------------
# Mono / stereo helpers
# -------------------------------------------------------------
def to_mono(audio: np.ndarray) -> np.ndarray:
    """
    Convert stereo → mono safely.
    """
    if audio.ndim == 1:
        return audio
    return audio.mean(axis=1)


def ensure_stereo(audio: np.ndarray) -> np.ndarray:
    """
    Convert mono → stereo safely.
    """
    if audio.ndim == 2:
        return audio
    return np.stack([audio, audio], axis=1)


# -------------------------------------------------------------
# Window generators
# -------------------------------------------------------------
def hann_window(size: int) -> np.ndarray:
    return np.hanning(size)


def hamming_window(size: int) -> np.ndarray:
    return np.hamming(size)


def blackman_window(size: int) -> np.ndarray:
    return np.blackman(size)


# -------------------------------------------------------------
# Interpolation curves
# -------------------------------------------------------------
def cosine_curve(n: int) -> np.ndarray:
    t = np.linspace(0, np.pi, n)
    return (1 - np.cos(t)) * 0.5


def sine_curve(n: int) -> np.ndarray:
    t = np.linspace(0, np.pi / 2, n)
    return np.sin(t)


def smoothstep_curve(n: int) -> np.ndarray:
    t = np.linspace(0, 1, n)
    return t * t * (3 - 2 * t)


# -------------------------------------------------------------
# Framing utilities
# -------------------------------------------------------------
def frame_audio(audio: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
    """
    Frame audio into overlapping windows.
    """
    if frame_size <= 0 or hop_size <= 0:
        raise ValueError("frame_size and hop_size must be positive")
    if len(audio) == 0:
        return np.empty((0, frame_size), dtype=np.float32)

    remaining = max(0, len(audio) - frame_size)
    num_frames = 1 + (remaining + hop_size - 1) // hop_size
    max_frames_with_audio = 1 + (len(audio) - 1) // hop_size
    num_frames = min(num_frames, max_frames_with_audio)
    frames = np.zeros((num_frames, frame_size), dtype=np.float32)

    for i in range(num_frames):
        start = i * hop_size
        end = start + frame_size
        chunk = audio[start:end]
        frames[i, :len(chunk)] = chunk

    return frames


def overlap_add(frames: np.ndarray, hop_size: int) -> np.ndarray:
    """
    Reconstruct audio from overlapping frames.
    """
    if frames.ndim != 2:
        raise ValueError("frames must be a two-dimensional array")
    if hop_size <= 0:
        raise ValueError("hop_size must be positive")
    if frames.shape[0] == 0:
        return np.empty(0, dtype=np.float32)

    frame_size = frames.shape[1]
    out_len = hop_size * (frames.shape[0] - 1) + frame_size
    out = np.zeros(out_len, dtype=np.float32)

    for i, frame in enumerate(frames):
        start = i * hop_size
        out[start:start + frame_size] += frame

    return out


# -------------------------------------------------------------
# Smoothing kernels
# -------------------------------------------------------------
def smoothing_kernel(kernel_type: str = "soft") -> np.ndarray:
    """
    Return a smoothing kernel for harmonic blending.
    """
    if kernel_type == "soft":
        return np.array([0.25, 0.5, 0.25])
    elif kernel_type == "wide":
        return np.array([0.1, 0.2, 0.4, 0.2, 0.1])
    else:
        return np.array([0.5, 0.5])


# -------------------------------------------------------------
# Utility: ms → samples
# -------------------------------------------------------------
def ms_to_samples(ms: float, sr: int) -> int:
    return int((ms / 1000.0) * sr)
