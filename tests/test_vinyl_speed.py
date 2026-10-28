"""Regression checks for the optional GUI-only 50% vinyl playback adapter."""
import numpy as np
import pytest

from isla.control import ControlService
from isla.playback import AudioError
from test_control import make_session


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
def test_half_speed_lowers_pitch_and_tempo_with_native_output_rate(rate, channels):
    c, _, files, *_ = make_session()
    service = ControlService(c)
    # Alternating signed samples make interpolation observable.
    mono = (np.arange(8192, dtype=np.float32) % 11 - 5) / 20
    source = np.repeat(mono[:, None], channels, axis=1)
    untouched = source.copy()
    c.player.install({"original": source, "velvet": source * .5}, rate)
    try:
        assert not service.snapshot().vinyl_slowdown
        assert "50%" in service.set_vinyl_slowdown(True)
        assert service.snapshot().vinyl_slowdown
        service.file_command("play")
        native = files.streams[-1]
        assert native.sr == rate, "Do not request unsupported half-rate hardware"

        # Uneven callbacks must preserve their pending half-frame across blocks.
        output = np.concatenate([native.pump(5), native.pump(7), native.pump(512)])
        expected = np.empty_like(output)
        sample_index = np.arange(len(output)) // 2
        expected[1::2] = source[sample_index[1::2]]
        expected[0] = source[0]
        for i in range(2, len(output), 2):
            j = i // 2
            expected[i] = (source[j - 1] + source[j]) / 2
        # The ALIVE GUI retains its independent 25% listening attenuation.
        np.testing.assert_allclose(output, expected * .25, atol=2e-7)
        assert c.player.position <= c.player.cursor
        assert c.player.cursor == (len(output) + 1) // 2
        np.testing.assert_array_equal(source, untouched)
    finally:
        service.shutdown()
        c.close()


def test_live_toggle_preserves_source_position_and_mode_and_restores_normal():
    c, _, files, *_ = make_session()
    service = ControlService(c)
    source = np.arange(8192, dtype=np.float32)[:, None] / 8192
    buffers = {"original": source, "velvet": source * .5}
    c.player.install(buffers, 48000)
    try:
        service.file_command("play")
        first = files.streams[-1]
        first.pump(512)
        service.file_command("mode velvet")
        first.pump(512)  # Complete the 5 ms crossfade.
        before = c.player.position
        assert service.set_vinyl_slowdown(True)
        assert first.closed
        assert len(files.streams) == 2
        assert c.player.mode == "velvet" and c.player.state == "playing"
        assert c.player.cursor == before
        assert service.snapshot().vinyl_slowdown
        slowed = files.streams[-1]
        slowed.pump(512)
        assert c.player.cursor == before + 256

        before_restore = c.player.position
        service.set_vinyl_slowdown(False)
        assert slowed.closed and c.player.cursor == before_restore
        assert not service.snapshot().vinyl_slowdown
        normal = files.streams[-1]
        normal.pump(512)
        assert c.player.cursor == before_restore + 512
        assert c.player.mode == "velvet"
        assert c.player.buffers["original"] is source
        assert c.player.buffers["velvet"] is buffers["velvet"]
    finally:
        service.shutdown()
        c.close()


def test_speed_selection_is_safe_and_research_remains_separate():
    c, _, _, *_ = make_session()
    service = ControlService(c)
    try:
        with pytest.raises(AudioError, match="prepare"):
            service.set_vinyl_slowdown(True)
        c.player.install({"original": np.zeros((8192, 2), np.float32)}, 48000)
        with pytest.raises(AudioError, match="on/off"):
            service.set_vinyl_slowdown(1)
        service.set_vinyl_slowdown(True)
        with pytest.raises(AudioError, match="Turn off Vinyl"):
            service.enter_remastered()
        service.set_vinyl_slowdown(False)
        assert not service.snapshot().vinyl_slowdown
    finally:
        service.shutdown()
        c.close()


@pytest.mark.parametrize('rate',[44100,48000])
def test_one_second_440hz_source_becomes_two_seconds_at_220hz(rate):
    c, _, files, *_ = make_session()
    c.player.backend.CallbackStop = files.CallbackStop
    service = ControlService(c)
    source = (.2*np.sin(2*np.pi*440*np.arange(rate)/rate)).astype(np.float32)[:,None]
    c.player.install({'original':source},rate)
    try:
        service.set_vinyl_slowdown(True)
        service.file_command('play')
        native = files.streams[-1]
        blocks = []
        while native.active:
            blocks.append(native.pump(512))
        output = np.concatenate(blocks)[:,0]
        assert 2*rate <= len(output) < 2*rate+512
        samples = output[:2*rate]
        spectrum = np.abs(np.fft.rfft(samples*np.hanning(len(samples))))
        frequency = np.fft.rfftfreq(len(samples),1/rate)[np.argmax(spectrum)]
        assert frequency == pytest.approx(220,abs=.5)
        np.testing.assert_allclose(samples[1::2],source[:,0]*.25,atol=2e-7)
        c.player.refresh()
        assert c.player.state == 'completed'
    finally:
        service.shutdown()
        c.close()
