"""Real Qt controls, actual spawned research DSP, fake audio transport."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog

from isla.preparation import Preparation
from test_qt_window import app, click, close_window, wait_ui, window_session
from tools.remastered_verify import fixture


def test_native_widgets_control_actual_render_without_restarting_audio(app, tmp_path, monkeypatch):
    path = tmp_path / 'research.wav'
    source = fixture(48000, 2)
    sf.write(path, source, 48000, subtype='FLOAT')
    w, c, live, files, *_ = window_session(app)
    try:
        assert not w.research_panel.isVisible()
        assert not w.apply_research.isEnabled()
        c.preparation_factory = Preparation
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(path), ''))
        click(app, w, w.open_file)
        wait_ui(app, lambda: w.state.can_play, timeout=15)
        click(app, w, w.play)
        stream = c.player.stream
        stream.pump()
        click(app, w, w.research_toggle)
        assert w.research_panel.isVisible()
        # Real keyboard events exercise both the combo and exact 5% ticks.
        w.research_mode.setFocus()
        QTest.keyClick(w.research_mode, Qt.Key.Key_End)
        assert w.research_mode.currentData() == 'melt'
        w.research_intensity.setFocus()
        QTest.keyClick(w.research_intensity, Qt.Key.Key_Home)
        for _ in range(10):
            QTest.keyClick(w.research_intensity, Qt.Key.Key_Right)
        assert w.research_intensity_value.text() == '50% permitted depth'
        cursor = c.player.cursor
        click(app, w, w.apply_research)
        assert w.state.research_pending and w.cancel_research.isEnabled()
        assert c.player.mode == 'original'
        wait_ui(app, lambda: w.state.research_active and not w.state.research_pending, timeout=15)
        assert w.state.research_mode == 'melt' and w.state.research_intensity == 50
        assert c.player.cursor == cursor and c.player.stream is stream and len(files.streams) == 1
        assert not live.streams and c.live.mode == 'bypass'
        # Detailed research metrics now live in the unified Diagnostics pane,
        # not a duplicate block under the ALIVE buttons.
        assert 'numerical screens PASS' in w.health.toPlainText()
        assert 'Remastered active: Melt at 50% depth' in w.health.toPlainText()
        assert w.research_intensity.value() == 10  # Polling preserves the draft.
        assert np.isfinite(stream.pump()).all()
        # Zero is a source copy, not a muted or FFT-reconstructed buffer.
        QTest.keyClick(w.research_intensity, Qt.Key.Key_Home)
        click(app, w, w.apply_research)
        wait_ui(app, lambda: w.state.research_intensity == 0 and not w.state.research_pending, timeout=15)
        assert c.player._selected.tobytes() == source.tobytes()
        click(app, w, w.file_modes['bypass'])
        assert not w.state.research_active and c.player.mode == 'original'
        assert c.player.stream is stream and len(files.streams) == 1
    finally:
        close_window(app, w, c)
