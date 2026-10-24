"""ALIVE acceptance with a deterministic PortAudio stand-in and real file DSP."""
from pathlib import Path
from types import SimpleNamespace
import time

import numpy as np
import pytest
import soundfile as sf

from drivers import cli
from drivers.api import IslaBuffer
from isla.playback import AudioError, BufferPlayer, SoundDeviceBackend
from isla.preparation import MODES, Preparation
from isla.terminal import TerminalController, run_terminal


class CallbackStop(Exception):
    pass


class FakeStream:
    def __init__(self, backend, sr, channels, callback, finished):
        self.backend = backend
        self.sr = sr
        self.channels = channels
        self.callback = callback
        self.finished = finished
        self.active = False
        self.closed = False
        self.time = 100.0
        self.dac_time = 100.0
        backend.streams.append(self)

    def start(self):
        self.active = True

    def pump(self, frames=512, status=False):
        data = np.full((frames, self.channels), np.nan, dtype=np.float32)
        try:
            self.callback(data, frames, SimpleNamespace(outputBufferDacTime=self.dac_time), status)
        except CallbackStop:
            self.active = False
            self.finished()
        self.time += frames / self.sr
        self.dac_time += frames / self.sr
        return data

    def abort(self):
        self.active = False
        self.finished()

    def close(self):
        assert not self.closed, "A stream must be closed exactly once"
        self.closed = True


class FakeBackend:
    CallbackStop = CallbackStop

    def __init__(self):
        self.streams = []

    def output_name(self):
        return "Test speakers"

    def open(self, samplerate, channels, callback, finished_callback):
        return FakeStream(self, samplerate, channels, callback, finished_callback)


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def buffers():
    return {name: np.full((4097, 2), index / 10, np.float32)
            for index, name in enumerate(("original", *MODES), 1)}


def test_play_complete_replay_and_owned_stream_cleanup(backend, buffers):
    player = BufferPlayer(backend)
    player.install(buffers, 44100)
    assert player.play() == "Playing original audio."
    stream = player.stream
    assert player.play() == "Already playing."
    assert len(backend.streams) == 1
    rendered = np.concatenate([stream.pump() for _ in range(9)])
    np.testing.assert_array_equal(rendered[:4097], buffers['original'])
    assert np.count_nonzero(rendered[4097:]) == 0
    player.refresh()
    assert player.state == "completed" and player.cursor == 4097
    assert stream.closed
    player.play()
    assert player.cursor == 0
    player.close()
    player.close()
    assert all(s.closed for s in backend.streams)


def test_pause_resume_uses_audible_clock_stop_resets(backend, buffers):
    player = BufferPlayer(backend)
    player.install(buffers, 44100)
    player.play()
    stream = player.stream
    stream.pump()
    # Simulate queued output: only 123 samples have reached the DAC.
    stream.time = stream.dac_time - (512 - 123) / 44100
    player.pause()
    assert player.cursor == 123 and player.state == "paused" and stream.closed
    assert player.pause() == "Playback is not playing."
    assert player.play() == "Playback resumed."
    np.testing.assert_array_equal(player.stream.pump(), buffers['original'][123:635])
    player.stop()
    assert player.cursor == 0 and player.state == "stopped"
    player.close()


def test_modes_crossfade_at_same_position_and_bypass_is_exact(backend, buffers):
    player = BufferPlayer(backend)
    player.install(buffers, 44100)
    player.play()
    player.stream.pump()
    for mode in (*MODES, "original"):
        cursor = player.cursor
        player.select(mode)
        data = player.stream.pump()
        assert player.cursor == cursor + 512
        assert data.shape == (512, 2)
        np.testing.assert_array_equal(data[len(player._fade):], buffers[mode][cursor + len(player._fade):cursor + 512])
        assert np.isfinite(data).all()
    assert len(backend.streams) == 1
    player.close()


def test_long_transition_spans_blocks_without_duration_change(backend):
    buffers = {"original": np.zeros((2048, 1), np.float32), "melt": np.ones((2048, 1), np.float32)}
    player = BufferPlayer(backend)
    player.install(buffers, 192000)
    player.play()
    player.stream.pump()
    player.select('melt')
    first, second = player.stream.pump(), player.stream.pump()
    np.testing.assert_allclose(np.concatenate([first, second])[:960, 0], player._fade[:, 0])
    player.close()


def test_repeated_commands_and_underrun(backend, buffers):
    player = BufferPlayer(backend)
    player.install(buffers, 44100)
    for _ in range(20):
        player.play()
        player.stream.pump(status=True)
        assert "underrun" in player.warning
        player.pause()
        player.play()
        player.stop()
        player.stop()
    player.close()
    assert len(backend.streams) == 40
    assert all(stream.closed for stream in backend.streams)


def test_output_failure_closes_partially_started_stream(backend, buffers, monkeypatch):
    player = BufferPlayer(backend)
    player.install(buffers, 44100)
    def fail_start(self):
        raise RuntimeError("device disconnected")
    monkeypatch.setattr(FakeStream, 'start', fail_start)
    with pytest.raises(AudioError, match="device disconnected"):
        player.play()
    assert player.state == 'stopped' and player.stream is None
    assert backend.streams[-1].closed
    player.close()


def test_unexpected_stream_stop_surfaces_warning(backend, buffers):
    player = BufferPlayer(backend)
    player.install(buffers, 44100)
    player.play()
    player.stream.active = False
    player.refresh()
    assert player.state == 'paused' and 'unexpectedly' in player.warning
    player.close()


class PendingPreparation:
    def __init__(self, path):
        self.path = Path(path)
        self.done = False
        self.state = 'Preparing VELVET...'
        self.closed = False
        self.result = None

    def poll(self):
        if self.result is not None:
            self.done = True
            return self.result

    def close(self):
        self.closed = True


def test_terminal_commands_paths_status_and_responsive_loading(backend, buffers):
    controller = TerminalController(backend, PendingPreparation)
    assert 'Loading' in controller.execute('LoAd "~/Music/my piano.wav"')
    assert str(controller.job.path) == '~/Music/my piano.wav'
    assert 'Preparing VELVET' in controller.execute('StAtUs')
    with pytest.raises(ValueError, match='Preparing'):
        controller.execute('play')
    assert 'reset' in controller.execute('help')
    job = controller.job
    job.result = buffers, 44100
    assert 'Playing original' in controller.execute('PLAY')
    for mode in MODES:
        assert f'{mode.upper()} enabled' in controller.execute(f'MODE {mode.upper()}')
        assert controller.player._selected is buffers[mode]
    assert 'Original audio' in controller.execute('BYPASS')
    assert controller.player._selected is buffers['original']
    status = controller.execute('status')
    assert all(s in status for s in ('my piano.wav', 'original', 'playing', 'Test speakers'))
    assert 'paused' in controller.execute('pause')
    assert 'resumed' in controller.execute('play')
    assert 'stopped' in controller.execute('stop')
    assert 'Goodbye' in controller.execute('EXIT')
    assert job.closed and controller.closed
    assert all(s.closed for s in backend.streams)


@pytest.mark.parametrize('line', ['dance', 'mode', 'mode invalid', 'mode melt extra', 'load', 'play extra', '"unterminated'])
def test_invalid_commands_are_actionable(backend, line):
    controller = TerminalController(backend)
    with pytest.raises(ValueError):
        controller.execute(line)
    controller.close()


def test_exit_cancels_pending_preparation_and_replacement_closes_old_job(backend):
    controller = TerminalController(backend, PendingPreparation)
    controller.execute('load one.wav')
    old = controller.job
    controller.execute('load two with spaces.wav')
    assert old.closed and str(controller.job.path) == 'two with spaces.wav'
    current = controller.job
    controller.execute('exit')
    assert current.closed


@pytest.mark.parametrize('ending', [EOFError, KeyboardInterrupt])
def test_terminal_eof_interrupt_cleanup(backend, ending):
    output = []
    def interrupt(prompt):
        raise ending
    assert run_terminal(interrupt, output.append, backend) == 0
    assert 'ISLA — ALIVE' in output[0]
    assert 'Resources released' in output[-1]


def test_cli_launch_and_preserve_required_offline_arguments(monkeypatch):
    monkeypatch.setattr('isla.terminal.run_terminal', lambda: 73)
    assert cli.main([]) == 73
    with pytest.raises(SystemExit) as error:
        cli.main(['--mode', 'velvet'])
    assert error.value.code == 2


def wait_ready(job):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = job.poll()
        if result is not None:
            return result
        time.sleep(.01)
    pytest.fail('Preparation did not finish')


@pytest.mark.parametrize('channels,sr', [(1, 8000), (2, 44100)])
def test_real_wav_preparation_every_mode_matches_existing_dsp(tmp_path, channels, sr):
    t = np.arange(sr // 8) / sr
    mono = np.concatenate((np.zeros(sr // 8), .2 * np.sin(2 * np.pi * 440 * t),
                           np.zeros(sr // 8), .3 * np.sin(2 * np.pi * 880 * t), np.zeros(13)))
    original = np.column_stack([mono * (1 - .2 * ch) for ch in range(channels)]).astype(np.float32)
    path = tmp_path / 'my piano.wav'
    sf.write(path, original, sr, subtype='FLOAT')
    job = Preparation(str(path))
    try:
        buffers, loaded_sr = wait_ready(job)
        assert loaded_sr == sr
        np.testing.assert_array_equal(buffers['original'], original)
        for mode in MODES:
            expected = IslaBuffer(mode=mode, sr=sr).process_buffer(original)
            assert buffers[mode].shape == original.shape
            np.testing.assert_array_equal(buffers[mode], expected.astype(np.float32))
        assert any(not np.array_equal(buffers['velvet'], buffers[mode]) for mode in ('legato', 'melt'))
    finally:
        directory = Path(job.directory.name)
        job.close()
        assert not directory.exists()


def test_short_wav_and_real_worker_cancel(tmp_path):
    path = tmp_path / 'short.wav'
    sf.write(path, np.zeros((1, 1), np.float32), 44100)
    job = Preparation(str(path))
    try:
        buffers, sr = wait_ready(job)
        assert all(buffer.shape == (1, 1) for buffer in buffers.values())
    finally:
        job.close()
    job = Preparation(str(path))
    process = job.process
    job.close()
    assert process._closed


def test_missing_invalid_empty_and_multichannel_files(tmp_path):
    with pytest.raises(ValueError, match='not found'):
        Preparation(str(tmp_path / 'missing.wav'))
    invalid = tmp_path / 'invalid.wav'
    invalid.write_text('this is not audio')
    with pytest.raises(ValueError, match='invalid audio'):
        Preparation(str(invalid))
    for frames, channels in [(0, 1), (100, 3)]:
        path = tmp_path / f'{frames}-{channels}.wav'
        sf.write(path, np.zeros((frames, channels)), 44100)
        with pytest.raises(ValueError, match='non-empty mono or stereo'):
            Preparation(str(path))


def test_nonfinite_file_worker_error_is_reported_and_cleaned(tmp_path, backend):
    path = tmp_path / 'nonfinite.wav'
    sf.write(path, np.array([np.nan, 0], np.float32), 44100, subtype='FLOAT')
    controller = TerminalController(backend)
    controller.execute(f'load "{path}"')
    directory = Path(controller.job.directory.name)
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            try:
                controller.poll()
            except ValueError as error:
                assert 'non-finite' in str(error)
                break
            time.sleep(.01)
        else:
            pytest.fail('Preparation error was not surfaced')
        assert controller.job is None and not directory.exists()
    finally:
        controller.close()


def test_real_offline_cli_roundtrip(tmp_path):
    path, output = tmp_path / 'input.wav', tmp_path / 'output.wav'
    sf.write(path, np.zeros((4410, 2)), 44100)
    assert cli.main(['--input', str(path), '--output', str(output), '--mode', 'velvet']) == 0
    data, sr = sf.read(output)
    assert sr == 44100 and data.shape == (4410, 2)
    assert cli.main(['--input', str(tmp_path / 'absent.wav'), '--output', str(output)]) == 1


def test_backend_missing_device_or_unsupported_settings(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError('no such device')
    device = SoundDeviceBackend.__new__(SoundDeviceBackend)
    device.sd = SimpleNamespace(query_devices=unavailable, check_output_settings=unavailable)
    with pytest.raises(AudioError, match='No output device'):
        device.output_name()
    with pytest.raises(AudioError, match='48000 Hz / 2 channel'):
        device.open(48000, 2, None, None)


def test_terminal_recovers_from_invalid_command_and_no_file(backend):
    commands = iter(('unknown', 'play', 'help', 'status', 'exit'))
    output = []
    assert run_terminal(lambda prompt: next(commands), output.append, backend) == 0
    assert any('Unknown command' in line for line in output)
    assert any('Load an audio file first' in line for line in output)
    assert 'Goodbye' in output[-1]


def test_exit_is_available_even_when_preparation_has_failed(backend):
    controller = TerminalController(backend, PendingPreparation)
    controller.execute('load one.wav')
    job = controller.job
    def failed_poll():
        raise ValueError('worker failure')
    job.poll = failed_poll
    assert 'Goodbye' in controller.execute('exit')
    assert job.closed


def test_disconnected_device_cleanup_still_closes_stream(backend, buffers, monkeypatch):
    player = BufferPlayer(backend)
    player.install(buffers, 44100)
    player.play()
    stream = player.stream
    def disconnected():
        raise RuntimeError('disconnected')
    monkeypatch.setattr(stream, 'abort', disconnected)
    player.close()
    assert stream.closed and player.stream is None and not player.buffers


def test_installed_module_and_console_entrypoints_enter_shell():
    import subprocess
    import sys

    for command in ([sys.executable, '-m', 'isla'], [str(Path(sys.executable).parent / 'isla')]):
        result = subprocess.run(command, input='help\nstatus\nexit\n', text=True,
                                capture_output=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'ISLA — ALIVE' in result.stdout
        assert 'load <path>' in result.stdout and 'Status: idle' in result.stdout
        assert 'Resources released.' in result.stdout
