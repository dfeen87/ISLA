"""Adversarial research publication, separate from production-only acceptance."""
import time

import numpy as np
import pytest

from test_remastered_preparation import ready_service


@pytest.mark.parametrize('bad', ['peak', 'report'])
def test_invalid_render_report_or_pcm_cannot_replace_active_audio(tmp_path, bad):
    s, c, files = ready_service(tmp_path)
    try:
        s.file_command('play')
        stream, selected, buffers = c.player.stream, c.player._selected, c.player.buffers
        s.prepare_remastered('velvet', 50)
        job = s.preview.job
        job.complete()
        if bad == 'peak':
            job.result[0][0, 0] = 1.5  # Child report still claims a safe peak.
        else:
            del job.result[1]['requested_depth']
        with pytest.raises(ValueError):
            s.poll()
        assert c.player._selected is selected and c.player.buffers is buffers
        assert c.player.stream is stream and not stream.closed
        assert job.closed and s.preview.job is None
        assert s.snapshot().research_stage == 'Failed'
        s.prepare_remastered('melt', 0)
        s.preview.job.complete()
        s.poll()
        assert s.snapshot().research_stage == 'Applying'
        stream.pump()
        s.poll()
        assert s.snapshot().research_stage == 'Completed'
        assert len(files.streams) == 1
    finally:
        s.shutdown()
        c.close()


def test_real_background_render_preserves_every_outgoing_playback_sample(tmp_path):
    from isla.remastered_preparation import RemasteredPreparation
    s, c, files = ready_service(tmp_path)
    s.preview.factory = RemasteredPreparation
    s._original_file_backend.CallbackStop = files.CallbackStop
    try:
        s.file_command('play')
        stream = c.player.stream
        s.prepare_remastered('melt', 50)
        count = 0
        while c.player.cursor < len(c.player._selected):
            s.poll()
            p = c.player
            start, selected, previous = p.cursor, p._selected, p._current
            expected = np.zeros((512, 2), np.float32)
            n = min(512, len(selected)-start)
            expected[:n] = selected[start:start+n]
            pos = 0 if selected is not previous else p._fade_pos
            fade_n = min(n, len(p._fade)-pos)
            if fade_n:
                expected[:fade_n] = (expected[:fade_n]*p._fade[pos:pos+fade_n] +
                    previous[start:start+fade_n]*p._inverse[pos:pos+fade_n])
            np.testing.assert_array_equal(stream.pump(), expected*.25)
            count += 1
            time.sleep(.01)  # Test-only pacing; not a native deadline assertion.
        deadline = time.monotonic()+10
        while s.preview.job is not None and time.monotonic()<deadline:
            s.poll()
            time.sleep(.01)
        assert s.preview.job is None and s.preview.applied.mode == 'melt'
        assert count > 100 and len(files.streams) == 1
        assert s._alive_gui_backend.underflows == s._alive_gui_backend.dac_gaps == 0
    finally:
        s.shutdown()
        c.close()
