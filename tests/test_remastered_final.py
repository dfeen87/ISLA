"""Explicit exclusive workspace restoration and stale-publication acceptance."""
import numpy as np
import pytest

from isla.playback import AudioError
from test_remastered_preparation import ready_service


@pytest.mark.parametrize('mode', ['original', 'velvet', 'legato', 'melt'])
@pytest.mark.parametrize('transport', ['playing', 'paused', 'stopped'])
def test_enter_cancel_exact_previous_mode_and_transport(tmp_path, mode, transport):
    s, c, files = ready_service(tmp_path)
    try:
        s.file_command('bypass' if mode == 'original' else 'mode '+mode)
        if transport != 'stopped':
            s.file_command('play')
            c.player.stream.pump()
            if transport == 'paused': s.file_command('pause')
        stream, cursor = c.player.stream, c.player.cursor
        s.enter_remastered()
        assert c.player.mode == 'original' and s.snapshot().research_previous_mode == mode
        assert s.snapshot().research_workspace
        for command in ('bypass', 'mode velvet', 'mode legato', 'mode melt'):
            with pytest.raises(AudioError, match='Return to Previous Mode'):
                s.file_command(command)
        s.prepare_remastered('velvet', 50)
        job = s.preview.job
        job.complete()  # Cancellation must win over a completed, unconsumed result.
        s.cancel_remastered()
        s.poll()
        assert job.closed and not s.snapshot().research_workspace
        assert c.player.mode == mode and c.player._selected is c.player.buffers[mode]
        assert c.player.stream is stream and c.player.cursor == cursor
        assert c.player.state == transport
        assert len(files.streams) == (transport != 'stopped')
    finally:
        s.shutdown()
        c.close()


def test_apply_save_return_and_repeated_cancel(tmp_path):
    import soundfile as sf
    import time
    s, c, files = ready_service(tmp_path)
    try:
        s.file_command('mode legato')
        s.file_command('play')
        c.player.stream.pump()
        for _ in range(4):
            s.enter_remastered()
            s.prepare_remastered('melt', 50)
            with pytest.raises(AudioError, match='preparation'):
                s.save_mix(tmp_path/'pending.wav')
            s.cancel_remastered()
            assert c.player.mode == 'legato'
        s.enter_remastered()
        s.prepare_remastered('velvet', 50)
        s.preview.job.complete()
        s.poll()
        assert s.snapshot().research_stage == 'Applying'
        c.player.stream.pump()
        s.poll()
        assert s.snapshot().research_stage == 'Completed'
        expected = c.player._selected.copy()
        s.set_alive_volume(50)
        s.save_mix(tmp_path/'remastered.wav')
        while s.mix_export.pending: time.sleep(.001)
        actual, _ = sf.read(tmp_path/'remastered.wav', dtype='float32', always_2d=True)
        np.testing.assert_array_equal(actual, expected)
        cursor = c.player.cursor
        s.return_previous_mode()
        assert s.snapshot().research_stage == 'Returning'
        assert c.player.mode == 'legato' and c.player.cursor == cursor
        c.player.stream.pump()
        s.poll()
        assert s.snapshot().research_stage == 'Returned'
        assert len(files.streams) == 1
    finally:
        s.shutdown()
        c.close()


@pytest.mark.parametrize('change', ['reload', 'stop', 'shutdown', 'foreign_install'])
def test_workspace_invalidation_never_restores_old_recording(tmp_path, change):
    s, c, _ = ready_service(tmp_path)
    try:
        s.file_command('mode melt')
        s.enter_remastered()
        s.prepare_remastered('velvet', 50)
        job = s.preview.job
        job.complete()
        if change == 'reload': s.load_file('another.wav')
        elif change == 'stop': s.file_command('stop')
        elif change == 'shutdown': s.shutdown()
        else:
            c.player.install({'original': np.zeros((8192, 2), np.float32)}, 48000)
            s.poll()
        assert job.closed and not s.preview.workspace
        if change == 'stop': assert c.player.mode == 'melt'
        else: assert c.player.mode == 'original'
        assert not any(name.startswith('remastered_') for name in c.player.buffers)
        if not s.closed:
            s.cancel_remastered()
            assert c.player.mode != 'melt' or change == 'stop'
    finally:
        if not s.closed: s.shutdown()
        c.close()


@pytest.mark.parametrize('bad', ['long', 'rate', 'channels', 'unprepared'])
def test_enter_admission_precedes_bypass_or_workspace_change(tmp_path, bad):
    s, c, _ = ready_service(tmp_path)
    try:
        s.file_command('mode legato')
        if bad == 'long': c.player.buffers['original'] = np.zeros((31*48000, 2), np.float32)
        elif bad == 'rate': c.player.sr = 32000
        elif bad == 'channels': c.player.buffers['original'] = np.zeros((8192, 3), np.float32)
        else: c.job.done = False
        selected = c.player._selected
        with pytest.raises(AudioError): s.enter_remastered()
        assert c.player.mode == 'legato' and c.player._selected is selected
        assert not s.preview.workspace
    finally:
        s.shutdown()
        c.close()


def test_failed_render_keeps_workspace_bypass_then_restores_and_can_retry(tmp_path):
    s, c, files = ready_service(tmp_path)
    try:
        s.file_command('mode legato')
        s.file_command('play')
        s.enter_remastered()
        s.prepare_remastered('melt', 50)
        job = s.preview.job
        job.complete()
        job.result[0][0, 0] = np.nan
        with pytest.raises(ValueError): s.poll()
        assert s.snapshot().research_stage == 'Failed'
        assert s.snapshot().research_workspace and c.player.mode == 'original'
        assert job.closed and 'remastered_melt' not in c.player.buffers
        s.cancel_remastered()
        assert c.player.mode == 'legato'
        s.enter_remastered()
        s.prepare_remastered('velvet', 0)
        s.preview.job.complete()
        s.poll()
        with pytest.raises(AudioError, match='Return to Previous Mode'):
            s.cancel_remastered()
        s.return_previous_mode()
        assert c.player.mode == 'legato' and len(files.streams) == 1
    finally:
        s.shutdown()
        c.close()
