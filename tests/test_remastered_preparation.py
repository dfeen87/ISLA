"""Real spawned DSP and adversarial command-worker publication lifecycles."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from isla.playback import AudioError
from isla.control import ControlService
from isla.remastered import RenderRequest, output_metrics, render_preview
from isla.remastered_preparation import RemasteredPreparation
from test_alive import wait_ready
from test_control import make_session
from tools.remastered_verify import fixture


@pytest.mark.parametrize('sr,channels', [(44100, 1), (44100, 2), (48000, 1), (48000, 2)])
def test_real_spawn_prepares_validated_float32_baseline_and_releases_files(tmp_path, sr, channels):
    source = tmp_path / 'original.npy'
    x = fixture(sr, channels)
    np.save(source, x)
    job = RemasteredPreparation(source, sr, RenderRequest('melt', 100))
    try:
        y, report = wait_ready(job)
        expected, _ = render_preview(x, sr, RenderRequest('melt', 100))
        np.testing.assert_array_equal(y, expected.astype(np.float32))
        assert y.dtype == np.float32 and not isinstance(y, np.memmap)
        assert report['numerical_pass'] and report['playback_output']['finite']
    finally:
        directory = Path(job.directory.name)
        job.close()
        job.close()
        assert not directory.exists()


@pytest.mark.parametrize('intensity', [0, 50, 100])
def test_hot_source_rejected_with_evidence_without_normalizing(tmp_path, intensity):
    source = tmp_path / 'hot.npy'
    np.save(source, np.ones((8192, 1), np.float32))
    job = RemasteredPreparation(source, 48000, RenderRequest('velvet', intensity))
    try:
        with pytest.raises(ValueError, match='peak screens'):
            wait_ready(job)
        assert Path(job.directory.name, 'report.json').is_file()
        assert not Path(job.directory.name, 'rendered.npy').exists()
    finally:
        job.close()


def test_duration_rate_admission_and_real_cancellation(tmp_path):
    source = tmp_path / 'original.npy'
    np.save(source, np.zeros((30*48000 + 1, 1), np.float32))
    with pytest.raises(ValueError, match='30 seconds'):
        RemasteredPreparation(source, 48000, RenderRequest('melt', 50))
    np.save(source, np.zeros((8192, 1), np.float32))
    with pytest.raises(ValueError, match='44.1/48'):
        RemasteredPreparation(source, 32000, RenderRequest('melt', 50))
    job = RemasteredPreparation(source, 48000, RenderRequest('melt', 50))
    process = job.process
    job.close()
    assert process._closed and not Path(job.directory.name).exists()


class DeferredRender:
    def __init__(self, source, sr, request):
        self.source, self.sr, self.request = source, sr, request
        self.state = 'Preparing test research render'
        self.closed = False
        self.result = None

    def poll(self):
        return self.result

    def complete(self):
        x = np.load(self.source)
        y, report = render_preview(x, self.sr, self.request)
        buffer = y.astype(np.float32)
        report['playback_output'] = output_metrics(x, buffer)
        self.result = buffer, report

    def close(self):
        self.closed = True


def ready_service(tmp_path):
    c, live, files, *_ = make_session()
    s = ControlService(c)
    s.load_file('source.wav')
    x = fixture(48000, 2)
    np.save(tmp_path / 'original.npy', x)
    c.job.directory = SimpleNamespace(name=str(tmp_path))
    c.job.result = {mode: x.copy() for mode in ('original', 'velvet', 'legato', 'melt')}, 48000
    s.poll()
    s.preview.factory = DeferredRender
    return s, c, files


def test_async_swap_preserves_cursor_stream_and_existing_crossfade(tmp_path):
    s, c, files = ready_service(tmp_path)
    try:
        s.file_command('play')
        stream = c.player.stream
        stream.pump()
        s.enter_remastered()
        s.prepare_remastered('legato', 50)
        job = s.preview.job
        for _ in range(3):
            s.poll()
            stream.pump()
            assert c.player.mode == 'original'
        cursor, previous = c.player.cursor, c.player._selected
        job.complete()
        s.poll()
        assert job.closed and s.preview.job is None
        assert c.player.cursor == cursor and c.player.stream is stream
        assert len(files.streams) == 1 and s.snapshot().research_active
        current = c.player._selected
        out = stream.pump()
        n = len(c.player._fade)
        expected = current[cursor:cursor+n]*c.player._fade + previous[cursor:cursor+n]*c.player._inverse
        # Research buffers/crossfade remain bit-exact; only the GUI-owned
        # PortAudio output is 25% of the preserved prepared result.
        np.testing.assert_array_equal(out[:n], expected * .25)
        np.testing.assert_array_equal(out[n:], current[cursor+n:cursor+512] * .25)
        # Pause retains position/state when a completed render is published.
        s.file_command('pause')
        paused = c.player.cursor
        s.enter_remastered()
        s.prepare_remastered('melt', 0)
        s.preview.job.complete()
        s.poll()
        assert c.player.cursor == paused and c.player.state == 'paused'
        assert c.player._selected.tobytes() == c.player.buffers['original'].tobytes()
        assert 'vetoed' in s.snapshot().research_summary
        assert s.snapshot().research_intensity == 0
    finally:
        s.shutdown()
        c.close()


@pytest.mark.parametrize('action', ['replacement', 'bypass', 'production', 'stop', 'reload', 'cancel', 'shutdown'])
def test_superseded_jobs_cannot_publish_stale_results(tmp_path, action):
    s, c, files = ready_service(tmp_path)
    try:
        s.enter_remastered()
        s.prepare_remastered('velvet', 25)
        old = s.preview.job
        old.complete()  # Ready but not yet polled; cancellation must still win.
        if action == 'replacement':
            s.enter_remastered()
            s.prepare_remastered('melt', 75)
        elif action == 'bypass':
            with pytest.raises(AudioError, match='Return to Previous Mode'):
                s.file_command(action)
            s.cancel_remastered()
        elif action == 'stop':
            s.file_command(action)
        elif action == 'production':
            with pytest.raises(AudioError, match='Return to Previous Mode'):
                s.file_command('mode legato')
            s.cancel_remastered()
        elif action == 'reload':
            s.load_file('new.wav')
        elif action == 'cancel':
            s.cancel_remastered()
        else:
            s.shutdown()
        assert old.closed and s.preview.job is not old
        if action != 'shutdown':
            s.poll()
        assert not c.player.mode.startswith('remastered_')
        assert not files.streams
    finally:
        if not s.closed:
            s.shutdown()
        c.close()


def test_failed_worker_and_bad_buffer_preserve_active_audio_and_allow_retry(tmp_path):
    s, c, files = ready_service(tmp_path)
    try:
        s.file_command('play')
        stream, selected = c.player.stream, c.player._selected
        for bad in ('worker', 'buffer'):
            s.enter_remastered()
            s.prepare_remastered('melt', 50)
            job = s.preview.job
            if bad == 'worker':
                def fail():
                    raise ValueError('render died')
                job.poll = fail
            else:
                job.complete()
                job.result[0][0, 0] = np.nan
            with pytest.raises(ValueError):
                s.poll()
            assert job.closed and s.preview.job is None
            assert c.player._selected is selected and c.player.stream is stream
            assert c.player.state == 'playing'
        s.enter_remastered()
        s.prepare_remastered('velvet', 25)
        s.preview.job.complete()
        s.poll()
        assert c.player.mode == 'remastered_velvet'
        assert len(files.streams) == 1
    finally:
        s.shutdown()
        c.close()
