"""
Python API driver for ISLA (formerly Phased-Music-Notes).

Provides:
    - smooth(): one-call file-based interface
    - IslaFile: OO file-based interface (PhasedNotes compatibility alias)
    - IslaBuffer: buffer-based interface (PhasedNotesBuffer compatibility alias)

It wraps the core engine in src/main.py so users never need
to touch internal DSP modules directly.
"""

from pathlib import Path
from typing import Union, BinaryIO

import numpy as np

from src.main import IslaMusicEngine


# ----------------------------------------------------------------------
# File-based functional API
# ----------------------------------------------------------------------
def smooth(input_path: Union[str, Path, BinaryIO],
           output_path: Union[str, Path, BinaryIO],
           mode: str = "velvet") -> None:
    """
    Smooth Audio Notes with a single function call.

    Parameters
    ----------
    input_path : str, Path, or file-like object
        Path to the input audio file.
    output_path : str, Path, or file-like object
        Path where the smoothed audio will be saved.
    mode : str
        Smoothing mode (e.g., velvet, legato, melt).
    """
    # Only convert to string if it is a Path object, to allow file-like objects
    if isinstance(input_path, Path):
        input_path = str(input_path)
    if isinstance(output_path, Path):
        output_path = str(output_path)

    engine = IslaMusicEngine(mode=mode)
    engine.smooth_file(input_path, output_path)


# ----------------------------------------------------------------------
# File-based OO API
# ----------------------------------------------------------------------
class IslaFile:
    """
    Object-oriented API wrapper for file-based processing.

    Example
    -------
        pn = IslaFile(mode="melt")
        pn.process("piano.wav", "piano_soft.wav")
    """

    def __init__(self, mode: str = "velvet"):
        self.mode = mode
        self.engine = IslaMusicEngine(mode=mode)

    def process(self,
                input_path: Union[str, Path, BinaryIO],
                output_path: Union[str, Path, BinaryIO]) -> None:
        if isinstance(input_path, Path):
            input_path = str(input_path)
        if isinstance(output_path, Path):
            output_path = str(output_path)
        self.engine.smooth_file(input_path, output_path)


# ----------------------------------------------------------------------
# Buffer-based API for DAW/VST integration
# ----------------------------------------------------------------------
class IslaBuffer:
    """
    Buffer-based DSP driver for DAW/VST integration.

    This class is intended to be called from a C++/pybind11 bridge,
    where audio buffers are passed as NumPy arrays.

    Example (Python-side)
    ---------------------
        pnb = IslaBuffer(mode="velvet", sr=44100)
        out = pnb.process_buffer(audio_np)
    """

    def __init__(self, mode: str = "velvet", sr: int = 44100):
        self.mode = mode
        self.sr = sr
        self.engine = IslaMusicEngine(mode=mode)

    def process_buffer(self, audio_buffer: np.ndarray) -> np.ndarray:
        """
        Process a NumPy audio buffer.

        Parameters
        ----------
        audio_buffer : np.ndarray
            Shape: (num_samples,) or (num_samples, num_channels)

        Returns
        -------
        np.ndarray
            Smoothed audio buffer with the same shape.
        """
        # Ensure we’re working with a NumPy array
        audio_buffer = np.asarray(audio_buffer)

        # Step 1: Detect note boundaries
        boundaries = self.engine.analyzer.detect_boundaries(audio_buffer, self.sr)

        # Step 2: Apply smoothing per boundary region
        softened = self.engine.smoother.apply(audio_buffer, boundaries, self.sr)

        # Step 3: Blend harmonics for gradual transitions
        final_output = self.engine.harmonics.blend(softened, self.sr)

        return final_output


# Legacy aliases keep existing scripts, pipeline adapters and integrations working.
PhasedNotes = IslaFile
PhasedNotesBuffer = IslaBuffer
