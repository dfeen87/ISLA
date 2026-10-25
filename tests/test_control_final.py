"""Output PCM acceptance outside frozen playback/DSP; no acoustic claims."""
import numpy as np
import pytest

from isla.control import ControlService
from isla.playback import AudioError
from isla.monitor_gain import MonitorVolume, ListeningGainDSP
from isla.listening_gain import GainRamp
from test_control import make_session


@pytest.mark.parametrize('rate', [44100, 48000])
@pytest.mark.parametrize('percent', [0, 25, 50, 100])
def test_dynamic_alive_gain_pcm_mode_transition_single_stream(rate, percent, tmp_path):
    c, _, files, *_ = make_session()
    s = ControlService(c)
    original = np.full((8192, 2), .4, np.float32)
    velvet = np.full((8192, 2), .2, np.float32)
    c.player.install({'original': original, 'velvet': velvet}, rate)
    try:
        assert s.snapshot().alive_volume == 25 and s.snapshot().monitor_volume == 50
        s.file_command('play')
        stream = files.streams[-1]
        np.testing.assert_array_equal(stream.pump(), original[:512] * .25)
        s.set_alive_volume(percent)
        # Simultaneous prepared-buffer crossfade and independent gain ramp.
        s.file_command('mode velvet')
        actual = stream.pump()
        expected = velvet[:512].copy()
        n = len(c.player._fade)
        expected[:n] = (velvet[:n] * c.player._fade + original[:n] * c.player._inverse)
        gain = np.full(512, percent / 100, np.float32)
        gain[:n] = .25 + (np.arange(1, n+1, dtype=np.float32) * ((percent/100-.25)/n))
        np.testing.assert_allclose(actual, expected * gain[:, None], atol=2e-8, rtol=0)
        np.testing.assert_array_equal(stream.pump(), velvet[:512] * (percent/100))
        assert s.snapshot().alive_applied_volume == pytest.approx(percent)
        assert c.player.stream is stream and len(files.streams) == 1
        np.testing.assert_array_equal(original, np.full_like(original, .4))
        np.testing.assert_array_equal(velvet, np.full_like(velvet, .2))
        target = tmp_path / 'mix.wav'
        s.save_mix(target)
        import time
        while s.mix_export.pending:
            time.sleep(.001)
        import soundfile as sf
        audio, _ = sf.read(target, dtype='float32', always_2d=True)
        np.testing.assert_array_equal(audio, velvet)  # listening gain excluded
    finally:
        s.shutdown()
        c.close()


@pytest.mark.parametrize('percent', [0, 25, 50, 100])
def test_live_post_dsp_gain_independent_from_capture(percent):
    class DSP:
        def __init__(self, *args): pass
        def process_block(self, x): return x * np.float32(.5)
    volume = MonitorVolume(50)
    processor = ListeningGainDSP(48000, 2, volume, delegate_factory=DSP)
    x = np.full((512, 2), .4, np.float32)
    volume.set_percent(percent)
    processor.process_block(x)
    out = processor.process_block(x)
    np.testing.assert_array_equal(out, x * .5 * (percent/100))
    np.testing.assert_array_equal(x, np.full_like(x, .4))
    assert processor._applied == pytest.approx(percent/100)


def test_ramp_persists_across_short_blocks_and_retargets_without_steps():
    ramp = GainRamp(48000, 100)
    pieces = []
    for size in (31, 7, 101, 13, 88, 99):
        out = np.ones((size, 1), np.float32)
        ramp.apply(out, 0)
        pieces.append(out[:, 0])
    actual = np.concatenate(pieces)
    expected = np.maximum(0, 1-np.arange(1, len(actual)+1)/240)
    np.testing.assert_allclose(actual, expected, atol=1e-7)
    assert not np.any(actual[239:])
    out = np.ones((11, 1), np.float32)
    ramp.apply(out, 100)
    previous = out[-1, 0]
    out.fill(1)
    ramp.apply(out, 0)
    assert abs(out[0, 0]-previous) <= 1/240
    assert 0 <= out.min() <= out.max() <= 1


def test_gain_bounds_and_export_waits_for_full_mode_fade(tmp_path):
    c, *_ = make_session()
    s = ControlService(c)
    c.player.install({name: np.full((8192, 2), .2, np.float32)
                      for name in ('original', 'velvet')}, 48000)
    try:
        for invalid in (True, -1, 101, .5):
            with pytest.raises(ValueError): s.set_alive_volume(invalid)
            with pytest.raises(ValueError): s.set_monitor_volume(invalid)
        s.file_command('play')
        s.file_command('mode velvet')
        c.player.stream.pump(64)
        with pytest.raises(AudioError, match='switch'):
            s.save_mix(tmp_path/'ambiguous.wav')
        assert 'transition pending' in s.snapshot().save_candidate
        c.player.stream.pump()
        assert 'velvet' in s.snapshot().save_candidate
    finally:
        s.shutdown()
        c.close()
