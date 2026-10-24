"""Development fixtures, not the frozen recorded-source candidate evaluation."""

import numpy as np
import pytest
from scipy.signal import find_peaks

from tools.resonance02.slowdown import stretch


def _tone(sr=16000, seconds=1.5, frequency=440.0, phase=0.0):
    return 0.2 * np.sin(2 * np.pi * frequency * np.arange(round(sr * seconds)) / sr + phase)


def _pitch_hz(signal, sr):
    segment = signal[len(signal) // 3 : 2 * len(signal) // 3]
    spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment)), n=8 * len(segment)))
    peak = np.argmax(spectrum[1:]) + 1
    logged = np.log(np.maximum(spectrum[peak - 1 : peak + 2], 1e-30))
    offset = 0.5 * (logged[0] - logged[2]) / (logged[0] - 2 * logged[1] + logged[2])
    return (peak + offset) * sr / (8 * len(segment))


def _stationary_ipd(signal, sr, frequency=440.0):
    segment = signal[len(signal) // 3 : 2 * len(signal) // 3]
    basis = np.exp(-2j * np.pi * frequency * np.arange(len(segment)) / sr)
    coefficients = np.sum(segment * np.hanning(len(segment))[:, None] * basis[:, None], axis=0)
    return np.angle(coefficients[0] * np.conj(coefficients[1]))


@pytest.mark.parametrize("ratio", [1.25, 1.50])
@pytest.mark.parametrize("protected", [False, True])
def test_sustained_pitch_and_exact_duration(ratio, protected):
    sr = 16000
    source = _tone(sr)
    output, diagnostic = stretch(source, sr, ratio, protected)
    cents = 1200 * np.log2(_pitch_hz(output, sr) / 440.0)
    assert abs(cents) <= 3.0
    assert len(output) == round(len(source) * ratio)
    assert diagnostic["duration_error_samples"] == 0
    assert diagnostic["finite"]
    assert diagnostic["output_sample_peak"] == np.max(np.abs(output))
    assert diagnostic["output_4x_peak_estimate"] > 0
    assert not diagnostic["amplitude_normalization"]
    assert not diagnostic["limiter_or_clipping"]


@pytest.mark.parametrize("ratio", [1.25, 1.50])
@pytest.mark.parametrize("channels", [1, 2])
def test_digital_silence_and_short_boundary_lengths(ratio, channels):
    for length in [0, 1, 3, 511, 512, 513, 2049]:
        output, diagnostic = stretch(np.zeros((length, channels)), 44100, ratio)
        assert output.shape == (round(length * ratio), channels)
        assert not output.size or np.max(np.abs(output)) <= 1e-12
        assert diagnostic["finite"]


@pytest.mark.parametrize("ratio", [1.25, 1.50])
@pytest.mark.parametrize("protected", [False, True])
def test_stereo_antiphase_and_stationary_interchannel_phase(ratio, protected):
    sr = 16000
    mono = _tone(sr)
    antiphase = np.column_stack((mono, -mono))
    output, diagnostic = stretch(antiphase, sr, ratio, protected)
    assert np.max(np.abs(output[:, 0] + output[:, 1])) <= 1e-12
    assert np.sqrt(np.mean(output[:, 0] ** 2)) > 0.05
    assert diagnostic["synthesis_coefficient_ipd_error_rad"] <= 1e-12
    stereo = np.column_stack((mono, _tone(sr, phase=0.7)))
    output, _ = stretch(stereo, sr, ratio, protected)
    difference = np.angle(np.exp(1j * (_stationary_ipd(output, sr) - _stationary_ipd(stereo, sr))))
    assert abs(difference) <= 0.05


def test_exact_bypass_determinism_and_protection_controls():
    rng = np.random.default_rng(20261024)
    source = rng.normal(0, 0.1, (2049, 2))
    bypass, diagnostic = stretch(source, 48000, 1)
    assert np.array_equal(bypass, source)
    assert not np.shares_memory(source, bypass)
    assert diagnostic["exact_bypass"]
    first, first_diagnostic = stretch(source, 48000, 1.25)
    second, second_diagnostic = stretch(source, 48000, 1.25)
    assert np.array_equal(first, second)
    assert first_diagnostic == second_diagnostic
    raw, raw_diagnostic = stretch(source, 48000, 1.25, False)
    disabled, _ = stretch(source, 48000, 1.25, True,
                          identity_phase_locking=False, transient_resets=False)
    assert np.array_equal(raw, disabled)
    assert not raw_diagnostic["identity_phase_locking"]
    assert not raw_diagnostic["transient_resets"]


@pytest.mark.parametrize("source,sr,ratio", [
    (np.zeros((16, 3)), 16000, 1.25),
    (np.array([np.nan]), 16000, 1.25),
    (np.zeros(16), 0, 1.25),
    (np.zeros(16), 16000.5, 1.25),
    (np.zeros(16), 16000, 1.2),
])
def test_invalid_input_rejected(source, sr, ratio):
    with pytest.raises(ValueError):
        stretch(source, sr, ratio)


@pytest.mark.parametrize("ratio", [1.25, 1.50])
def test_repeated_impulse_registered_event_count_and_timing(ratio):
    """Keep the strict transient screen; do not loosen it after a failure."""
    sr = 16000
    source = np.zeros(round(1.4 * sr))
    event_samples = np.round(np.array([0.25, 0.65, 1.05]) * sr).astype(int)
    source[event_samples] = 0.5
    output, _ = stretch(source, sr, ratio, True)
    peaks, _ = find_peaks(np.abs(output), distance=round(0.10 * sr),
                          prominence=0.10 * np.max(np.abs(output)))
    expected = np.round(event_samples * ratio).astype(int)
    assert len(peaks) == len(expected), f"extra/missing events: observed={peaks}, expected={expected}"
    error_seconds = np.abs(peaks - expected) / sr
    assert np.max(error_seconds) <= 0.010, f"event timing errors seconds={error_seconds}"
