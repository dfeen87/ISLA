"""Real Qt radio-button regression for the ALIVE vinyl slowdown workflow."""
import pytest

pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from test_control import prepared_buffers
from test_qt_window import app, close_window, wait_ui, window_session


def test_vinyl_radio_switches_50_to_100_and_keeps_mode_buttons(app):
    w, controller, _, files, *_ = window_session(app)
    try:
        assert w.vinyl_slowdown.text() == "Vinyl-style slowdown"
        assert w.vinyl_rate.text() == "100%"
        assert not w.vinyl_slowdown.isEnabled()
        w.submit("load", "vinyl.wav")
        wait_ui(app, lambda: not w.busy)
        controller.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.can_play and w.vinyl_slowdown.isEnabled())

        QTest.mouseClick(w.play, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: not w.busy and w.state.file_state.value == "File playing")
        QTest.mouseClick(w.vinyl_slowdown, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: not w.busy and w.state.vinyl_slowdown)
        assert w.vinyl_slowdown.isChecked()
        assert w.vinyl_rate.text() == "50%"
        assert w.file_modes["velvet"].isEnabled()
        assert not w.try_remastered_first.isEnabled()
        assert len(files.streams) == 2  # Speed reopens only the ALIVE output.

        QTest.mouseClick(w.file_modes["velvet"], Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: not w.busy and controller.player.mode == "velvet")
        # Let the source-mode crossfade finish before changing speed again.
        files.streams[-1].pump(512)
        QTest.mouseClick(w.vinyl_slowdown, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: not w.busy and not w.state.vinyl_slowdown)
        assert not w.vinyl_slowdown.isChecked()
        assert w.vinyl_rate.text() == "100%"
        assert controller.player.mode == "velvet"
    finally:
        close_window(app, w, controller)
