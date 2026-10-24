"""Regression gates for ISLA's new identity and retained legacy Python API."""

import isla
import phased_music_notes
from isla import SmoothPhase, HarmonicBlender, NoteAnalyzer, PhaseSmoother
from isla.harmonics import HarmonicBlender as IslaHarmonicBlender
from phased_music_notes.harmonics import HarmonicBlender as LegacyHarmonicBlender
from drivers.api import IslaBuffer, IslaFile, PhasedNotesBuffer, PhasedNotes
from src.main import IslaMusicEngine, PhasedMusicEngine
from drivers.cli import create_parser


def test_isla_public_api_and_legacy_imports():
    assert isla.__version__ == phased_music_notes.__version__ == "3.1.0"
    assert isla.SmoothPhase is phased_music_notes.SmoothPhase
    assert SmoothPhase(mode="velvet").mode == "velvet"
    assert HarmonicBlender is IslaHarmonicBlender is LegacyHarmonicBlender
    assert NoteAnalyzer is not None and PhaseSmoother is not None


def test_legacy_python_engine_and_driver_aliases():
    assert IslaMusicEngine is PhasedMusicEngine
    assert IslaBuffer is PhasedNotesBuffer
    assert IslaFile is PhasedNotes
    assert IslaBuffer(mode="melt", sr=44100).engine.mode == "melt"


def test_isla_command_line_identity():
    parser = create_parser()
    assert parser.prog == "isla"
