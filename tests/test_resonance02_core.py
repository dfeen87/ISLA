"""Independent development checks; these are not the primary listening evaluation."""
from dataclasses import replace

import numpy as np
import pytest

from tools.resonance02 import core


def _tone(sr=48000, seconds=.5):
    t = np.arange(round(sr * seconds)) / sr
    return (.12 * np.cos(2 * np.pi * 3520 * t) +
            .04 * np.cos(2 * np.pi * 7053 * t))[:, None]


def _controlled_spectra(frames=24, channels=2):
    """Supply known spectral observations to isolate operations from admission."""
    cfg = core.Config()
    bins = cfg.frame // 2 + 1
    X = np.ones((frames, channels, bins), dtype=complex)
    if channels == 2:
        X[:, 1, 1:-1] *= .7 * np.exp(.4j)
    features = np.zeros((frames, 10))
    features[:, 5] = 1.  # Explicitly trusted observations, no attack or silence.
    states = np.zeros((frames, len(core.REGIMES)))
    states[:, core.REGIMES.index('sustain')] = 1.
    analysis = dict(X=X, A=np.abs(X), pooled=np.sqrt(np.mean(np.abs(X)**2, axis=1)),
                    features=features, states=states,
                    frequency=np.broadcast_to(2*np.pi*np.arange(bins)/cfg.frame,
                                              X.shape).copy(),
                    reliable=np.ones(X.shape, dtype=bool),
                    window=.5-.5*np.cos(2*np.pi*np.arange(cfg.frame)/cfg.frame))
    source = np.zeros(((frames-3)*cfg.hop, channels))
    return source, analysis


def _capture_spectra(monkeypatch):
    captured = []
    original = core.istft

    def reconstruct(X, *args, **kwargs):
        captured.append(X.copy())
        return original(X, *args, **kwargs)

    monkeypatch.setattr(core, 'istft', reconstruct)
    return captured


@pytest.mark.parametrize('length', [0, 1, 511, 512, 513, 2049, 12017])
@pytest.mark.parametrize('channels', [1, 2])
def test_float64_wola_reconstructs_boundaries_without_losing_samples(length, channels):
    x = np.random.default_rng(17).normal(0, .1, (length, channels))
    if length:
        x[0] = .4
        x[-1] = -.3
    X, _, window = core.stft(x)
    y = core.istft(X, length, window)
    assert y.shape == x.shape
    assert np.max(np.abs(x-y), initial=0.) <= 1e-10


@pytest.mark.parametrize('sr', [44100, 48000])
@pytest.mark.parametrize('length', [0, 1, 513, 4097])
def test_bypass_and_all_noops_are_exact_independent_copies(sr, length):
    x = np.random.default_rng(23).normal(0, .1, (length, 2))
    if length:
        x[0, 0] = -0.
    for mode, variant in [('bypass', 'governed')] + [(m, 'noop') for m in core.MODES]:
        y, _ = core.render(x, sr, mode, variant)
        assert y.dtype == x.dtype
        assert y.tobytes() == x.tobytes()
        assert not np.shares_memory(x, y)


@pytest.mark.parametrize('mode', core.MODES)
@pytest.mark.parametrize('sr', [44100, 48000])
def test_stereo_relationships_and_silent_channel_are_preserved(mode, sr):
    mono = _tone(sr)[:, 0]
    for x, relation in [(np.column_stack((mono, mono)), 'same'),
                        (np.column_stack((mono, -mono)), 'opposite'),
                        (np.column_stack((mono, np.zeros_like(mono))), 'silent')]:
        y, d = core.render(x, sr, mode)
        assert np.any(d['control'] > 0), 'The processor must be exercised.'
        if relation == 'same':
            assert np.array_equal(y[:, 0], y[:, 1])
        elif relation == 'opposite':
            assert np.array_equal(y[:, 0], -y[:, 1])
        else:
            assert np.count_nonzero(y[:, 1]) == 0
        assert np.isfinite(y).all()


@pytest.mark.parametrize('mode', core.MODES)
@pytest.mark.parametrize('sr', [44100, 48000])
def test_long_gap_clears_history_and_cannot_generate_a_tail(mode, sr):
    x = np.concatenate((_tone(sr, .3), np.zeros((round(.3*sr), 1)), _tone(sr, .2)))
    a = core.analyze(x, sr)
    y, d = core.render(x, sr, mode, analysis=a)
    settled = y[round(.4*sr):round(.55*sr)]
    assert np.max(np.abs(settled), initial=0.) <= 1e-10
    quiet = a['features'][:, 8].astype(bool)
    assert quiet.any()
    assert np.count_nonzero(a['resonance'][quiet]) == 0
    assert np.count_nonzero(d['control'][quiet]) == 0
    for variant in core.VARIANTS:
        silence, _ = core.render(np.zeros((2051, 2)), sr, mode, variant)
        assert np.count_nonzero(silence) == 0


@pytest.mark.parametrize('mode', core.MODES)
@pytest.mark.parametrize('variant', core.VARIANTS)
def test_replay_is_bit_exact_and_separate_segments_do_not_share_state(mode, variant):
    x = _tone()
    first, d1 = core.render(x, 48000, mode, variant)
    core.render(np.random.default_rng(1).normal(0, .1, (8701, 2)), 44100, mode, variant)
    second, d2 = core.render(x, 48000, mode, variant)
    assert first.tobytes() == second.tobytes()
    assert d1.keys() == d2.keys()
    for key in d1:
        assert np.array_equal(d1[key], d2[key]), key


@pytest.mark.parametrize('mode', core.MODES)
def test_cached_analysis_and_input_are_reusable_without_mutation(mode):
    x = _tone()
    source_bytes = x.tobytes()
    analysis = core.analyze(x, 48000)
    snapshot = {key: value.copy() for key, value in analysis.items()}
    cached, _ = core.render(x, 48000, mode, analysis=analysis)
    direct, _ = core.render(x, 48000, mode)
    assert np.array_equal(cached, direct)
    assert x.tobytes() == source_bytes
    for key in snapshot:
        assert np.array_equal(snapshot[key], analysis[key]), key


@pytest.mark.parametrize('sr', [44100, 48000])
def test_phase_prediction_distinguishes_stationary_tone_from_seeded_noise(sr):
    t = np.arange(round(.5*sr))/sr
    tone = (.1*np.cos(2*np.pi*3520*t))[:, None]
    noise = np.random.default_rng(20261024).normal(0, .07, tone.shape)
    tone_analysis = core.analyze(tone, sr)
    noise_analysis = core.analyze(noise, sr)
    central = (tone_analysis['time'] > .15) & (tone_analysis['time'] < .4)
    # A weak directional development check, not a universal perceptual score.
    assert np.median(tone_analysis['features'][central, 3]) > np.median(noise_analysis['features'][central, 3])


@pytest.mark.parametrize('sr', [44100, 48000])
@pytest.mark.parametrize('mode', core.MODES)
def test_control_bounds_and_registered_slew_except_explicit_veto(sr, mode):
    x = np.concatenate((_tone(sr, .24), .001*_tone(sr, .12), _tone(sr, .24)))
    a = core.analyze(x, sr)
    cfg = core.Config()
    y, d = core.render(x, sr, mode, analysis=a)
    u = d['control']
    maximum = getattr(cfg, mode+'_depth')
    assert np.isfinite(y).all() and np.isfinite(a['features']).all()
    assert np.isfinite(a['resonance']).all()
    assert np.all(a['states'] >= 0) and np.all(a['states'] <= 1)
    np.testing.assert_allclose(a['states'].sum(axis=1), 1., atol=1e-14, rtol=0)
    assert np.all(u >= 0) and np.all(u <= maximum)
    veto = ((a['features'][:, 8] != 0) |
            (a['features'][:, 6] >= .5) |
            (a['features'][:, 5] < .2))
    assert np.all(u[veto] == 0)
    ordinary = ~veto
    delta = np.abs(np.diff(u, prepend=0.))
    assert np.all(delta[ordinary] <= maximum*cfg.hop/sr/cfg.recovery_s + 1e-14)
    assert d['gain_min'] >= cfg.gain_min
    assert d['gain_max'] <= cfg.gain_max
    assert d['phase_max'] <= cfg.phase_max_rad


@pytest.mark.parametrize('sr', [44100, 48000])
def test_recovery_time_is_in_seconds_at_both_sample_rates(sr):
    cfg = core.Config()
    x, a = _controlled_spectra()
    for mode in core.MODES:
        _, d = core.render(x, sr, mode, 'fixed', analysis=a)
        maximum = getattr(cfg, mode+'_depth')
        reached = np.flatnonzero(d['control'] >= maximum-1e-14)[0]
        recovery_seconds = (reached+1)*cfg.hop/sr
        assert cfg.recovery_s <= recovery_seconds <= cfg.recovery_s+cfg.hop/sr


def test_legato_decay_time_tracks_configured_seconds_and_sr(monkeypatch):
    captured = _capture_spectra(monkeypatch)
    for sr in (44100, 48000):
        for tau in (.04, .08):
            cfg = replace(core.Config(), legato_memory_s=tau)
            x, a = _controlled_spectra(frames=80)
            transition = 24
            a['X'][transition:] *= .75
            a['A'] = np.abs(a['X'])
            a['pooled'] = np.sqrt(np.mean(a['A']**2, axis=1))
            core.render(x, sr, 'legato', 'fixed', cfg=cfg, analysis=a)
            gain = np.abs(captured[-1][:, 0, 200]/a['X'][:, 0, 200])
            residual = np.log(gain[transition:])
            assert residual[0] > 0
            assert np.all(np.diff(residual) <= 1e-12)
            crossing = np.flatnonzero(residual <= residual[0]/np.e)[0]
            observed_tau = crossing*cfg.hop/sr
            assert abs(observed_tau-tau) <= cfg.hop/sr


def test_velvet_diffuses_valley_and_protected_peak_with_correct_sign(monkeypatch):
    captured = _capture_spectra(monkeypatch)
    x, a = _controlled_spectra()
    a['X'][:, :, 300:303] *= np.array([1., .75, 1.])
    a['X'][:, :, 400:403] *= np.array([1., 1.5, 1.])
    a['A'] = np.abs(a['X'])
    a['pooled'] = np.sqrt(np.mean(a['A']**2, axis=1))
    core.render(x, 48000, 'velvet', 'fixed', analysis=a)
    ratio = captured[-1][-1]/a['X'][-1]
    assert np.all(np.real(ratio[:, 301]) > 1), 'Positive log curvature must fill the valley.'
    assert np.all(np.real(ratio[:, 401]) < 1), 'Negative log curvature must attenuate the peak.'
    assert np.max(np.abs(np.imag(ratio))) <= 1e-12


@pytest.mark.parametrize('mode', core.MODES)
def test_unsupported_spectral_bins_remain_exactly_empty_and_gains_are_bounded(monkeypatch, mode):
    captured = _capture_spectra(monkeypatch)
    x, a = _controlled_spectra()
    a['X'][:, :, 100:120] = 0.
    a['X'][12:, :, 300] *= .01  # Challenge history gain with an existing, weak component.
    a['A'] = np.abs(a['X'])
    a['pooled'] = np.sqrt(np.mean(a['A']**2, axis=1))
    _, diagnostic = core.render(x, 48000, mode, 'fixed', analysis=a)
    Y = captured[-1]
    assert np.count_nonzero(Y[:, :, 100:120]) == 0
    supported = a['A'] > 0
    ratio = np.abs(Y[supported]/a['X'][supported])
    cfg = core.Config()
    assert ratio.min() >= cfg.gain_min-1e-12
    assert ratio.max() <= cfg.gain_max+1e-12
    if mode == 'legato':
        assert diagnostic['gain_limit_frames'] > 0, 'This case must exercise the positive-gain ceiling.'


def test_melt_changes_only_shared_phase_and_reliability_loss_clears_offset(monkeypatch):
    captured = _capture_spectra(monkeypatch)
    x, a = _controlled_spectra(frames=24)
    a['frequency'][3:, :, 200] += .001
    a['reliable'][15:, :, 200] = False
    core.render(x, 48000, 'melt', 'fixed', analysis=a)
    Y = captured[-1]
    np.testing.assert_allclose(np.abs(Y), a['A'], atol=1e-12, rtol=0)
    assert np.max(np.abs(Y[4:15, :, 200]-a['X'][4:15, :, 200])) > 1e-4
    assert np.array_equal(Y[15:, :, 200], a['X'][15:, :, 200])
    assert np.array_equal(Y[:, :, 0], a['X'][:, :, 0])
    assert np.array_equal(Y[:, :, -1], a['X'][:, :, -1])
    original_ipd = np.angle(a['X'][:, 0]*np.conj(a['X'][:, 1]))
    resulting_ipd = np.angle(Y[:, 0]*np.conj(Y[:, 1]))
    assert np.max(np.abs(core.principal(resulting_ipd-original_ipd))) <= 1e-12


@pytest.mark.parametrize('source,sr', [
    (np.zeros(16), 48000),
    (np.zeros((16, 3)), 48000),
    (np.zeros((16, 1)), 16000),
    (np.array([[np.nan]]), 48000),
    (np.array([[np.inf]]), 48000),
    (np.array([[-np.inf]]), 48000),
])
def test_invalid_format_or_nonfinite_input_is_rejected_even_in_bypass(source, sr):
    with pytest.raises(ValueError):
        core.render(source, sr, 'bypass')


def test_unknown_mode_and_variant_rejected():
    with pytest.raises(ValueError):
        core.render(_tone(), 48000, 'unknown')
    with pytest.raises(ValueError):
        core.render(_tone(), 48000, 'velvet', 'unknown')
