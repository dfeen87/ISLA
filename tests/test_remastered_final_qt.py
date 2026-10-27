"""Explicit workspace native Qt acceptance; no physical-device claim."""
from types import SimpleNamespace
import numpy as np
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_qt_window import app, window_session, close_window, wait_ui, click
from test_remastered_preparation import DeferredRender
from tools.remastered_verify import fixture


def test_remastered_first_shortcut_enters_workspace_without_traditional_mode_click(app, tmp_path):
    w, c, _, files, *_ = window_session(app)
    try:
        w.submit('load', 'short.wav')
        wait_ui(app, lambda: not w.busy)
        x = fixture(48000, 2)
        np.save(tmp_path/'original.npy', x)
        c.job.directory = SimpleNamespace(name=str(tmp_path))
        c.job.result = {mode: x.copy() for mode in ('original', 'velvet', 'legato', 'melt')}, 48000
        wait_ui(app, lambda: w.state.can_play)
        w.worker.service.preview.factory = DeferredRender
        assert w.try_remastered_first.isEnabled()
        # Remastered is available before a conventional mode is selected.
        click(app, w, w.play)
        assert c.player.mode == 'original'
        click(app, w, w.try_remastered_first)
        wait_ui(app, lambda: not w.busy and w.state.research_workspace)
        assert c.player.mode == 'original'
        assert w.state.research_previous_mode == 'original'
        assert not w.try_remastered_first.isEnabled()
        assert not any(button.isEnabled() for button in w.file_modes.values())
        click(app, w, w.apply_research)
        assert w.state.research_pending
        click(app, w, w.cancel_research)
        assert c.player.mode == 'original' and not w.state.research_workspace
        assert w.try_remastered_first.isEnabled()
    finally:
        close_window(app, w, c)


def test_browsing_does_not_enter_and_exclusive_apply_return_is_explicit(app, tmp_path):
    w, c, _, files, *_ = window_session(app)
    try:
        w.submit('load', 'source.wav')
        wait_ui(app, lambda: not w.busy)
        x = fixture(48000, 2)
        np.save(tmp_path/'original.npy', x)
        c.job.directory = SimpleNamespace(name=str(tmp_path))
        c.job.result = {mode: x.copy() for mode in ('original', 'velvet', 'legato', 'melt')}, 48000
        wait_ui(app, lambda: w.state.can_play)
        w.worker.service.preview.factory = DeferredRender
        click(app, w, w.file_modes['melt'])
        click(app, w, w.play)
        stream = c.player.stream
        stream.pump()
        assert w.research_panel.isVisible()
        assert c.player.mode == 'melt' and not w.state.research_workspace
        assert not w.apply_research.isEnabled()
        button = w.enter_research
        QTest.mousePress(button, Qt.MouseButton.LeftButton)
        QTest.qWait(180)
        assert button.isDown()
        QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: not w.busy and w.state.research_workspace)
        assert c.player.mode == 'original'
        assert all(not b.isEnabled() for b in w.file_modes.values())
        # The always-visible panel must not disturb the active research state.
        assert w.research_panel.isVisible()
        assert w.state.research_workspace and c.player.mode == 'original'
        click(app, w, w.apply_research)
        assert w.state.research_pending and not w.save_mix_button.isEnabled()
        assert 'Unavailable' in w.state.save_candidate
        click(app, w, w.cancel_research)
        assert c.player.mode == 'melt' and not w.state.research_workspace
        click(app, w, w.enter_research)
        click(app, w, w.apply_research)
        w.worker.service.preview.job.complete()
        wait_ui(app, lambda: w.state.research_active)
        stream.pump()
        wait_ui(app, lambda: w.state.research_stage == 'Completed')
        assert not w.cancel_research.isEnabled()
        assert w.return_research.isEnabled() and w.save_mix_button.isEnabled()
        assert 'remastered_velvet' in w.health.toPlainText()
        click(app, w, w.return_research)
        assert c.player.mode == 'melt' and not w.state.research_workspace
        assert c.player.stream is stream and len(files.streams) == 1
        assert w.file_modes['legato'].isEnabled()
    finally:
        close_window(app, w, c)
