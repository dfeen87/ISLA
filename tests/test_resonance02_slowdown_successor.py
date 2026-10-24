"""Post-freeze engineering checks; no recorded-source research gate is replaced."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import find_peaks

from tools.resonance02 import slowdown as frozen
from tools.resonance02.slowdown_successor import stretch
from test_resonance02_slowdown import _pitch_hz


@pytest.mark.parametrize("ratio", [1.25, 1.50])
@pytest.mark.parametrize("sr", [16000, 44100, 48000])
def test_isolated_impulses_across_hop_offsets_and_boundaries(ratio, sr):
    # Include the edges of the protection window, hop, and output crop. Boundary
    # events require argmax: scipy.find_peaks deliberately excludes endpoints.
    length = 8193
    positions = [0, 1, 511, 512, 513, 1023, 1024, 1025, 1100, 1535,
                 1536, 2047, 2048, 2049, 4000, 4095, 4096, length - 2, length - 1]
    for event in positions:
        source = np.zeros(length)
        source[event] = .5
        output, diagnostic = stretch(source, sr, ratio)
        expected = round(event * ratio)
        assert abs(np.argmax(abs(output)) - expected) / sr <= .010
        assert np.count_nonzero(abs(output) > .05) == 1
        assert abs(output[expected] - .5) < 1e-12
        assert np.sum(np.delete(output, expected) ** 2) < 1e-20
        assert len(output) == round(length * ratio)
        assert diagnostic["successor_applied"]
        assert diagnostic["minimum_retained_window_square_sum"] > 1e-12


@pytest.mark.parametrize("ratio", [1.25, 1.50])
@pytest.mark.parametrize("sr", [16000, 44100, 48000])
def test_shared_schedule_preserves_transient_polarity_and_balance(ratio, sr):
    events = np.round(np.array([.25, .65, 1.05]) * sr).astype(int)
    source = np.zeros((round(1.4 * sr), 2))
    source[events] = [.5, -.2]
    output, diagnostic = stretch(source, sr, ratio)
    expected = np.round(events * ratio).astype(int)
    peaks, _ = find_peaks(abs(output[:, 0]), distance=round(.1 * sr),
                          prominence=.1 * max(abs(output[:, 0])))
    assert len(peaks) == len(expected)
    assert max(abs(peaks - expected)) / sr <= .010
    assert np.max(abs(output[:, 1] + .4 * output[:, 0])) < 1e-12
    swapped, other = stretch(source[:, ::-1], sr, ratio)
    assert np.max(abs(swapped[:, ::-1] - output)) < 1e-12
    assert diagnostic["transient_anchor_samples"] == other["transient_anchor_samples"]
    assert diagnostic["synthesis_coefficient_ipd_error_rad"] < 1e-12


@pytest.mark.parametrize("ratio", [1.25, 1.50])
@pytest.mark.parametrize("kind", ["gaussian", "noise_packet", "tone_attack"])
def test_short_nonimpulse_attacks_preserve_count_and_registered_timing(ratio, kind):
    sr = 16000
    events = np.round(np.array([.25, .65, 1.05]) * sr).astype(int)
    source = np.zeros(round(1.4 * sr))
    if kind == "gaussian":
        packet = .5 * np.exp(-.5 * (np.arange(-16, 17) / 4.) ** 2)
    elif kind == "noise_packet":
        packet = np.random.default_rng(20261024).normal(0, .2, 33) * np.hanning(33)
    else:
        t = np.arange(128) / sr
        packet = .5 * np.exp(-t * 500) * np.cos(2 * np.pi * 1800 * t)
    peak = int(np.argmax(abs(packet)))
    for event in events:
        source[event - peak:event - peak + len(packet)] += packet
    output, _ = stretch(source, sr, ratio)
    peaks, _ = find_peaks(abs(output), distance=round(.1 * sr), prominence=.1 * max(abs(output)))
    expected = np.round(events * ratio).astype(int)
    assert len(peaks) == len(expected)
    assert max(abs(peaks - expected)) / sr <= .010


@pytest.mark.parametrize("ratio", [1.25, 1.50])
def test_dense_detected_anchors_are_explicitly_unsupported(ratio):
    source = np.zeros(9000)
    source[[2500, 5500]] = .5
    output, diagnostic = stretch(source, 16000, ratio)
    original, _ = frozen.stretch(source, 16000, ratio)
    assert diagnostic["unsupported_dense_anchor_samples"] == [2500, 5500]
    assert not diagnostic["successor_applied"]
    assert np.array_equal(output, original)
    assert "INCOMPLETE" in diagnostic["gate_status"]


@pytest.mark.parametrize("ratio", [1.25, 1.50])
def test_reset_disabled_controls_retain_frozen_audio(ratio):
    source = np.random.default_rng(20261024).normal(0, .1, (9000, 2))
    for protected, locking in [(False, False), (False, True), (True, False), (True, True)]:
        output, diagnostic = stretch(source, 48000, ratio, protected,
            identity_phase_locking=locking, transient_resets=False)
        original, _ = frozen.stretch(source, 48000, ratio, protected,
            identity_phase_locking=locking, transient_resets=False)
        assert np.array_equal(output, original)
        assert not diagnostic["successor_applied"]


@pytest.mark.parametrize("ratio", [1.25, 1.50])
def test_nonzero_short_inputs_have_safe_window_alignment(ratio):
    for length in [1, 2, 3, 511, 512, 513, 1023, 1024, 1025, 2049]:
        for position in {0, length // 2, length - 1}:
            source = np.zeros(length)
            source[position] = .5
            output, diagnostic = stretch(source, 16000, ratio)
            assert len(output) == round(length * ratio)
            assert diagnostic["finite"]
            assert abs(output[round(position * ratio)] - .5) < 1e-12


@pytest.mark.parametrize("ratio", [1.25, 1.50])
def test_actual_variable_synthesis_increments_preserve_tonal_pitch(ratio):
    sr, frequency = 16000, 233.0
    source = .008 * np.sin(2 * np.pi * frequency * np.arange(round(1.4 * sr)) / sr)
    source[np.round(np.array([.25, .65, 1.05]) * sr).astype(int)] += .8
    output, diagnostic = stretch(source, sr, ratio)
    assert diagnostic["successor_applied"]
    assert diagnostic["synthesis_hop_max"] > round(frozen.ANALYSIS_HOP * ratio)
    segment = output[round(.8 * sr * ratio):round(.9 * sr * ratio)]
    assert abs(1200 * np.log2(_pitch_hz(segment, sr) / frequency)) <= 3.0



def _neutralize_release_version(content):
    """Ignore only the release-number literal, never other frozen Python code."""
    normalized, count = re.subn(
        rb'(?m)^__version__ = "[^"\r\n]+"$',
        b'__version__ = "<release-version>"',
        content,
    )
    assert count == 1, "expected exactly one top-level __version__ declaration"
    return normalized


def test_release_version_exception_rejects_nonversion_changes():
    original = b'__version__ = "3.1.1"\nfrom .dsl import SmoothPhase\n'
    bumped = b'__version__ = "3.2.0"\nfrom .dsl import SmoothPhase\n'
    tampered = b'__version__ = "3.2.0"\nfrom .dsl import DifferentEngine\n'
    assert _neutralize_release_version(original) == _neutralize_release_version(bumped)
    assert _neutralize_release_version(original) != _neutralize_release_version(tampered)
    with pytest.raises(AssertionError, match="exactly one"):
        _neutralize_release_version(b'from .dsl import SmoothPhase\n')


def test_all_original_freeze_hashes_remain_intact():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "docs/research/phase-governed-resonance-02/FREEZE.json").read_text())

    # Post-freeze application work legitimately changed these two production
    # entry points: terminal.py gained the GUI launcher; the legacy package
    # initializer changed its public release-number literal for v3.2.0.
    # Verify their ORIGINAL bytes against the immutable freeze baseline.
    historical_paths = {"isla/terminal.py", "phased_music_notes/__init__.py"}
    for name, expected in manifest["code_and_protocol"].items():
        if name in historical_paths:
            content = subprocess.check_output(
                ["git", "show", f"{manifest['baseline']}:{name}"], cwd=root
            )
        else:
            # Every frozen DSP, protocol and research path still must match
            # its original hash in the CURRENT working tree.
            content = (root / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected, name

        if name == "phased_music_notes/__init__.py":
            # A release bump is allowed, not an arbitrary edit to legacy API
            # imports or exports. Existing version tests check the live value.
            current = (root / name).read_bytes()
            assert _neutralize_release_version(current) == _neutralize_release_version(
                content
            ), "legacy package initializer changed beyond __version__"
