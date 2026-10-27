"""Debounced native widget edits, mode exclusivity and held-click acceptance."""
import threading

import numpy as np
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from test_qt_window import app, window_session, close_window, wait_ui, click
from test_control import prepared_buffers
from isla.control import UIState


def test_automatic_sliders_are_independent_and_do_not_cancel_held_press(app):
    w, c, _, files, *_ = window_session(app)
    calls = []
    request = w.worker.request_volume
    def recorded(kind, value):
        calls.append((kind, value))
        request(kind, value)
    w.worker.request_volume = recorded
    try:
        assert not any(b.text() == 'Apply Volume' for b in w.findChildren(QPushButton))
        assert w.alive_volume.value() == 25 and w.monitor_volume.value() == 50
        assert w.alive_volume_value.alignment() == Qt.AlignmentFlag.AlignCenter
        assert w.monitor_volume_value.alignment() == Qt.AlignmentFlag.AlignCenter
        w.submit('load', 'source.wav')
        wait_ui(app, lambda: not w.busy)
        x = np.full((8192, 2), .4, np.float32)
        c.job.result = {name: x.copy() for name in ('original', 'velvet', 'legato', 'melt')}, 48000
        wait_ui(app, lambda: w.state.can_play)
        click(app, w, w.play)
        # Rapid values coalesce to one scalar per control at the 80 ms cadence.
        for percent in range(101):
            w.alive_volume.setValue(percent)
            w.monitor_volume.setValue(100-percent)
        w.alive_volume.setValue(50)
        w.monitor_volume.setValue(25)
        button = w.file_modes['legato']
        QTest.mousePress(button, Qt.MouseButton.LeftButton)
        QTest.qWait(260)  # Volume mailbox and five status refreshes during press.
        assert button.isDown() and button.isEnabled()
        QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: not w.busy and w.state.file_mode == 'legato'
                and w.state.alive_volume == 50 and w.state.monitor_volume == 25)
        assert calls == [('alive_volume', 50), ('volume', 25)]
        c.player.stream.pump()
        np.testing.assert_array_equal(c.player.stream.pump(), x[:512]*.5)
        assert len(files.streams) == 1
        # Focus and old snapshots must never overwrite the latest keyboard edit.
        w.alive_volume.setFocus()
        QTest.keyClick(w.alive_volume, Qt.Key.Key_Home)
        for _ in range(50): QTest.keyClick(w.alive_volume, Qt.Key.Key_Right)
        w.close_button.setFocus()
        QTest.qWait(180)
        assert w.alive_volume.value() == 50
        click(app, w, w.mute_volume)
        wait_ui(app, lambda: w.state.monitor_volume == 0)
        click(app, w, w.mute_volume)
        wait_ui(app, lambda: w.state.monitor_volume == 25)
        assert w.state.alive_volume == 50
    finally:
        close_window(app, w, c)



@pytest.mark.parametrize('command,mode', [('play', 'original'), ('mode', 'melt')])
def test_pr68_slider_click_same_tick_reaches_first_audio_callback(app, command, mode):
    """A visible pending ALIVE level must precede Play or the next mode fade.

    The 80 ms debounce can otherwise leave the first output callback at the
    *previous* volume even though the slider visibly says the new value.
    Stop the timer to make this exact same-tick ordering deterministic.
    """
    w, c, _, files, *_ = window_session(app)
    try:
        w.submit('load', 'source.wav')
        wait_ui(app, lambda: not w.busy)
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        if command == 'mode':
            click(app, w, w.play)
            files.streams[-1].pump()
            # Begin from explicit digital silence, without reopening audio.
            w.alive_volume.setValue(0)
            w._flush_volumes()
            wait_ui(app, lambda: w.state.alive_volume == 0)
            files.streams[-1].pump()
            assert c.player.backend.applied_percent == pytest.approx(0)
            expected = .3  # prepared_buffers()['melt'] has value 0.3
            target = 100
            button = w.file_modes['melt']
        else:
            expected = 0.
            target = 0
            button = w.play

        w.alive_volume.setValue(target)
        assert w.volume_timer.isActive()
        w.volume_timer.stop()  # Guarantee no asynchronous 80 ms flush.
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: not w.busy and w.state.file_mode == mode
                and w.state.alive_volume == target)
        assert c.player.backend.output_level_percent == target
        assert len(files.streams) == 1
        out = files.streams[-1].pump()
        np.testing.assert_allclose(out[-64:], expected, atol=1e-7, rtol=0)
        assert w.state.file_mode == mode
        # Mode choice must never reopen the already running output stream.
    finally:
        close_window(app, w, c)


def test_volume_mailboxes_stay_bounded_while_control_command_is_blocked(app):
    w, c, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    original = w.worker.service.file_command
    def blocked(cmd):
        entered.set()
        assert release.wait(3)
        return original(cmd)
    w.worker.service.file_command = blocked
    try:
        w.submit('file', 'stop')
        assert entered.wait(1)
        for percent in range(101):
            w.alive_volume.setValue(percent)
            w.monitor_volume.setValue(100-percent)
            w._flush_volumes()
        assert len(w.worker._volume_targets) == 2
        assert w.worker.commands.qsize() == 0
        assert w.alive_volume.value() == 100 and w.monitor_volume.value() == 0
        release.set()
        wait_ui(app, lambda: not w.busy and w.state.alive_volume == 100 and w.state.monitor_volume == 0)
    finally:
        release.set()
        close_window(app, w, c)


