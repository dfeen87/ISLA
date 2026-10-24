"""ISLA — public Python audio DSP interface.

The original phased_music_notes modules remain available for compatibility.
No DSP algorithms are duplicated by this entry point.
"""
from phased_music_notes import __version__
from phased_music_notes.dsl import SmoothPhase
from phased_music_notes.analyzer import NoteAnalyzer
from phased_music_notes.smoother import PhaseSmoother
from phased_music_notes.harmonics import HarmonicBlender

__all__ = ["__version__", "SmoothPhase", "NoteAnalyzer", "PhaseSmoother", "HarmonicBlender"]
