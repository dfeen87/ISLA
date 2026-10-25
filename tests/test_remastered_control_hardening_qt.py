"""Held research preparation gestures remain separate from production tests."""
import numpy as np
from types import SimpleNamespace

import pytest
pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from test_qt_window import app, window_session, close_window, wait_ui, click


def test_prepare_and_cancel_mouse_presses_survive_periodic_refresh(app, tmp_path):
    from test_remastered_preparation import DeferredRender
    from tools.remastered_verify import fixture
    w, c, _, files, *_ = window_session(app)
    try:
        w.submit('load', 'source.wav')
        wait_ui(app, lambda: not w.busy and c.job is not None)
        x = fixture(48000, 2)
        np.save(tmp_path / 'original.npy', x)
        c.job.directory = SimpleNamespace(name=str(tmp_path))
        c.job.result = {name: x.copy() for name in ('original', 'velvet', 'legato', 'melt')}, 48000
        wait_ui(app, lambda: w.state.can_play)
        w.worker.service.preview.factory = DeferredRender
        click(app, w, w.play)
        stream, selected = c.player.stream, c.player._selected
        click(app, w, w.research_toggle)
        click(app, w, w.enter_research)
        for button in (w.apply_research, w.cancel_research):
            assert button.isEnabled()
            QTest.mousePress(button, Qt.MouseButton.LeftButton)
            QTest.qWait(180)
            assert button.isDown()
            QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
            wait_ui(app, lambda: not w.busy)
            if button is w.apply_research:
                assert w.state.research_pending
                job = w.worker.service.preview.job
                for _ in range(3):
                    stream.pump()
            else:
                assert not w.state.research_pending and w.state.research_stage == 'Canceled'
                assert job.closed
        assert c.player.stream is stream and c.player._selected is selected
        assert len(files.streams) == 1
    finally:
        close_window(app, w, c)
