"""Actual governed math at all required intensities and formats."""
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
from pathlib import Path

import numpy as np
import pytest

from isla.remastered import BASELINE_DEPTHS, CORE_SHA256, RenderRequest, render_preview
from tools.remastered_verify import fixture
from tools.resonance02 import core


@pytest.mark.parametrize('sr', [44100, 48000])
@pytest.mark.parametrize('channels', [1, 2])
@pytest.mark.parametrize('mode', core.MODES)
@pytest.mark.parametrize('intensity', [0, 25, 50, 75, 100])
def test_depth_matrix_against_frozen_equations(sr, channels, mode, intensity):
    x = fixture(sr, channels)
    before = x.tobytes()
    request = RenderRequest(mode, intensity)
    cfg = replace(core.Config(), **{mode + '_depth': BASELINE_DEPTHS[mode] * (intensity / 100)})
    expected, diagnostic = core.render(x, sr, mode, cfg=cfg)
    y, report = render_preview(x, sr, request)
    replay, replay_report = render_preview(x, sr, request)
    # Both raw and float32 prepared outputs are exactly the reference in this
    # environment; no loose allclose can hide output-amplitude/wet-dry mixing.
    np.testing.assert_array_equal(y, expected)
    assert y.tobytes() == replay.tobytes() and report == replay_report
    assert before == x.tobytes()
    assert not np.shares_memory(x, y)
    assert report['requested_depth'] == request.depth
    assert report['applied_depth_max'] == np.max(diagnostic['control'])
    assert report['vetoed_frames'] == diagnostic['fallback_frames'] > 0
    assert report['numerical_pass'] and all(report['checks'].values())
    if intensity == 0:
        assert y.dtype == x.dtype and y.tobytes() == before
    else:
        assert report['applied_depth_max'] > 0, 'Exercise actual processing.'
        assert not np.array_equal(y, x)
    if intensity == 100:
        baseline, _ = core.render(x, sr, mode)
        assert y.tobytes() == baseline.tobytes()


@pytest.mark.parametrize('mode', core.MODES)
def test_configuration_changes_only_selected_depth_and_is_immutable(mode):
    baseline = asdict(core.Config())
    for intensity in range(0, 101, 5):
        request = RenderRequest(mode, intensity)
        cfg = request.configuration()
        expected = dict(baseline, **{mode + '_depth': BASELINE_DEPTHS[mode] * (intensity / 100)})
        assert asdict(cfg) == expected
        with pytest.raises(FrozenInstanceError):
            cfg.recovery_s = 1
        with pytest.raises(FrozenInstanceError):
            request.intensity = 5
    assert asdict(core.Config()) == baseline
    assert hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest() == CORE_SHA256


@pytest.mark.parametrize('intensity', [-5, 101, 7, 2.5, '50', True, None])
def test_invalid_slider_values_rejected(intensity):
    with pytest.raises(ValueError, match='5% increments'):
        RenderRequest('melt', intensity)


@pytest.mark.parametrize('mode', core.MODES)
@pytest.mark.parametrize('sr', [44100, 48000])
@pytest.mark.parametrize('relation', ['identical', 'opposite', 'silent'])
def test_stereo_deterministic_relationships_and_no_generated_silence(mode, sr, relation):
    mono = fixture(sr, 1, np.float64)[:, 0]
    second = mono if relation == 'identical' else -mono if relation == 'opposite' else np.zeros_like(mono)
    x = np.column_stack((mono, second))
    for intensity in (0, 25, 50, 75, 100):
        y, report = render_preview(x, sr, RenderRequest(mode, intensity))
        if relation == 'identical':
            assert np.array_equal(y[:, 0], y[:, 1])
        elif relation == 'opposite':
            assert np.array_equal(y[:, 0], -y[:, 1])
        else:
            assert np.count_nonzero(y[:, 1]) == 0
        assert np.max(np.abs(y[round(sr*.79):round(sr*.85)])) < 1e-10
        assert report['checks']['veto_zero']


@pytest.mark.parametrize('dtype', [np.float32, np.float64])
@pytest.mark.parametrize('mode', core.MODES)
def test_zero_is_bit_exact_including_signed_zero_and_one_sample(dtype, mode):
    for x in (np.array([[-0., .2]], dtype=dtype), np.zeros((2049, 2), dtype=dtype)):
        y, report = render_preview(x, 44100, RenderRequest(mode, 0))
        assert y.tobytes() == x.tobytes() and y.dtype == x.dtype
        assert report['applied_depth_max'] == 0


@pytest.mark.parametrize('x,sr', [(np.zeros((0, 1)), 44100), (np.zeros((10, 3)), 48000),
    (np.zeros((10, 1)), 22050), (np.array([[np.nan]]), 48000)])
def test_invalid_source_fails_without_silent_format_conversion(x, sr):
    with pytest.raises(ValueError):
        render_preview(x, sr, RenderRequest('velvet', 50))


def test_fixed_phase_and_gain_ceilings_do_not_scale_with_intensity():
    for mode in core.MODES:
        for intensity in (0, 25, 50, 75, 100):
            cfg = RenderRequest(mode, intensity).configuration()
            assert (cfg.gain_min, cfg.gain_max, cfg.phase_max_rad) == (.8, 1.188502227, .1)


@pytest.mark.parametrize('sr', [44100, 48000])
@pytest.mark.parametrize('channels', [1, 2])
@pytest.mark.parametrize('mode', core.MODES)
def test_float64_baseline_equivalence_for_independent_stereo(sr, channels, mode):
    x = fixture(sr, channels, np.float64)
    if channels == 2:
        t = np.arange(len(x)) / sr
        x[:, 1] = .7*x[:, 1] + .02*np.sin(2*np.pi*1733*t + .4)
    y, report = render_preview(x, sr, RenderRequest(mode, 100))
    baseline, _ = core.render(x, sr, mode)
    assert y.tobytes() == baseline.tobytes() and y.dtype == baseline.dtype
    assert report['numerical_pass']
