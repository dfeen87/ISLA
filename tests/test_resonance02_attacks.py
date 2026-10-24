"""Falsification fixtures for timing, rank ambiguity and pooled stereo evidence."""
import numpy as np
import pytest

from tools.resonance02.attacks import assess_attacks, original_references


def _burst(sr=44100):
    rng = np.random.default_rng(712)
    x = np.zeros((round(.3*sr), 1))
    start, size = round(.1*sr), round(.035*sr)
    x[start:start+size, 0] = rng.normal(0, .1, size)*np.hanning(2*size)[size:]
    return x


@pytest.mark.parametrize("sr", [44100, 48000])
@pytest.mark.parametrize("direction", [-1, 1])
def test_known_sample_shift_is_detected_with_correct_sign(sr, direction):
    x = _burst(sr)
    delay = direction*round(.005*sr)
    y = np.zeros_like(x)
    if delay > 0:
        y[delay:] = x[:-delay]
    else:
        y[:delay] = x[-delay:]
    row = assess_attacks(x, y, sr, [.1])[0]
    assert row["waveform_lag_samples"] == delay
    assert row["waveform_lag_ms"] == pytest.approx(delay*1000/sr)
    assert "waveform_displacement" in row["labels"]
    assert row["timing_gate"] == "FAIL"
    assert row["waveform_ncc"]["maximum"] > .9999


def test_competing_slope_peak_rank_flip_is_unresolved_at_zero_waveform_lag():
    sr = 48000
    t = np.arange(round(.3*sr))/sr
    first = np.exp(-.5*((t-.1)/.00045)**2)
    second = np.exp(-.5*((t-.116)/.00045)**2)
    x = (first+.99*second)[:, None]
    y = (.99*first+second)[:, None]
    row = assess_attacks(x, y, sr, [.1])[0]
    assert row["waveform_lag_samples"] == 0
    assert row["waveform_ncc"]["maximum"] > .999
    assert row["competing_peak_ambiguity"]
    assert row["peak_rank_flip"]
    assert row["unresolved"]
    assert "detector_disagreement" in row["labels"]
    assert "waveform_displacement" not in row["labels"]
    assert abs(row["slope_peak_shift_ms"]) == pytest.approx(16., abs=.1)
    assert len(row["original_slope_peaks"]) >= 2


def test_antiphase_stereo_is_not_collapsed_to_silence():
    x = _burst()
    stereo = np.concatenate((x, -x), axis=1)
    row = assess_attacks(stereo, stereo, 44100, [.1])[0]
    assert row["waveform_lag_samples"] == 0
    assert row["waveform_ncc"]["maximum"] > .999999
    assert row["first_10ms_energy_gain_db"] == pytest.approx(0.)
    assert row["novelty_reference_seconds"] is not None


def test_level_change_is_separate_from_displacement():
    x = _burst()
    y = x*10**(3/20)
    row = assess_attacks(x, y, 44100, [.1])[0]
    assert row["waveform_lag_samples"] == 0
    assert row["first_10ms_energy_gain_db"] == pytest.approx(3.)
    assert row["energy_gate"] == "FAIL"
    assert "attack_energy_change" in row["labels"]
    assert "waveform_displacement" not in row["labels"]


def test_reference_selection_uses_original_only_and_replays():
    x = _burst()
    a = assess_attacks(x, x, 44100)
    b = assess_attacks(x, x*.7, 44100)
    assert a
    assert [r["reference_seconds"] for r in a] == original_references(x, 44100)
    assert [r["reference_seconds"] for r in a] == [r["reference_seconds"] for r in b]
    assert b == assess_attacks(x, x*.7, 44100)
    assert all(not r["physical_strike_truth"] for r in a)


def test_silence_has_no_invented_references_or_valid_timing():
    x = np.zeros((4410, 2))
    assert assess_attacks(x, x, 44100) == []
    row = assess_attacks(x, x, 44100, [.05])[0]
    assert row["waveform_lag_ms"] is None
    assert row["timing_gate"] == "UNRESOLVED"
    assert row["first_10ms_energy_gain_db"] is None


def test_invalid_shape_nonfinite_or_reference_is_rejected():
    x = _burst()
    with pytest.raises(ValueError):
        assess_attacks(x, x[:-1], 44100)
    with pytest.raises(ValueError):
        assess_attacks(x, x*np.nan, 44100)
    with pytest.raises(ValueError):
        assess_attacks(x, x, 44100, [-1])
    with pytest.raises(ValueError):
        assess_attacks(x, x, 0)
