"""Independent development oracles for measurements, never candidate tuning."""
import json

import numpy as np
import pytest

from tools.resonance02.measure import beat_metrics, metrics, reference


def _tone(sr=48000):
    # The registered .5 s development tone plus explicit known silent guards.
    t = np.arange(sr//2)/sr
    signal = .1*np.sin(2*np.pi*440*t)
    return np.pad(signal, (round(.125*sr), round(.125*sr)))[:, None]


def _cell(name="development_control"):
    return dict(name=name, kind="synthetic", events_seconds=[])


def test_exact_bypass_measurements_are_zero_and_json_finite():
    x = _tone()
    cell = _cell()
    result = metrics(x, x.copy(), 48000, cell, reference(x, 48000, cell))
    assert result["finite"] and result["same_length"]
    assert result["relative_waveform_rms"] == 0
    assert result["spectral_log_envelope_rms"] == 0
    assert result["rms_gain_db"] == 0
    assert result["max_frame_energy_ratio"] == pytest.approx(1.)
    assert result["settled_tail_peak"] == 0
    assert result["sample_peak"] == np.max(np.abs(x))
    # An oversampled estimate is measured, with no claim it is a certified bound.
    assert np.isfinite(result["oversampled_4x_peak"])
    assert result["screen_failures"] == []
    json.dumps(result, allow_nan=False)


def test_stereo_phase_preserved_and_inverted_are_distinguishable():
    mono = _tone()[:, 0]
    x = np.column_stack((mono, .7*mono))
    cell = _cell()
    ref = reference(x, 48000, cell)
    unchanged = metrics(x, x, 48000, cell, ref)
    altered = x.copy()
    altered[:, 1] *= -1
    changed = metrics(x, altered, 48000, cell, ref)
    assert unchanged["stereo_ipd_rms_rad"] == 0
    assert unchanged["balance_delta_db"] == 0
    assert changed["stereo_ipd_rms_rad"] > 3.
    assert changed["balance_delta_db"] == pytest.approx(0.)
    assert "stereo_ipd" in changed["screen_failures"]
    json.dumps(changed, allow_nan=False)


def test_silent_stereo_channel_has_undefined_correlation_without_nan():
    mono = _tone()[:, 0]
    x = np.column_stack((mono, np.zeros_like(mono)))
    cell = _cell()
    result = metrics(x, x, 48000, cell, reference(x, 48000, cell))
    assert result["stereo_correlation_delta"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("base,delta,tau", [(440., .2, None), (3520., 3., 6.)])
def test_known_twenty_second_beating_has_independent_spacing_and_envelope_oracles(base, delta, tau):
    sr = 48000
    t = np.arange(20*sr)/sr
    signal = .12*(np.cos(2*np.pi*base*t)+np.cos(2*np.pi*(base+delta)*t))
    if tau:
        signal *= np.exp(-t/tau)
    x = np.pad(signal, (6000, 6000))[:, None]
    result = beat_metrics(x, x.copy(), sr, dict(base_hz=base, delta_hz=delta, tau_s=tau))
    assert abs(result["spacing_error_hz"]) < 1e-5
    assert abs(result["beat_frequency_error_hz"]) < 1e-4
    assert result["detrended_envelope_correlation"] == pytest.approx(1.)
    assert result["amplitude_modulation_relative_rms"] == 0
    if tau:
        assert result["fitted_tau_s"] == pytest.approx(tau, abs=1e-4)
    json.dumps(result, allow_nan=False)
