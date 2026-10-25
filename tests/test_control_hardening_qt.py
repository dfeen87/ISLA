"""Held native gestures and PCM evidence; no physical Mac audio claim."""
from dataclasses import replace

import numpy as np
import pytest
import threading

pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from test_qt_window import app, window_session, close_window, wait_ui, click
from isla.control import UIState
from test_live import BLOCK, PassThrough, wait_for, warmup


def test_volume_keyboard_edit_auto_applies_and_survives_focus_loss_and_refresh(app):
    w, c, *_ = window_session(app)
    try:
        w.monitor_volume.setFocus()
        QTest.keyClick(w.monitor_volume, Qt.Key.Key_Home)
        for _ in range(25):
            QTest.keyClick(w.monitor_volume, Qt.Key.Key_Right)
        assert w.monitor_volume.value() == 25
        w.research_toggle.setFocus()
        QTest.qWait(180)  # At least three real 50 ms refreshes before release.
        assert w.monitor_volume.value() == 25
        wait_ui(app, lambda: not w.busy and w.state.monitor_volume == 25)
        processor = c.live.processor_factory(48000, 2)
        # The actual output adapter consumes the command, not just the label.
        processor.delegate = type('Dry', (), {'process_block': lambda self, x: x.copy()})()
        np.testing.assert_array_equal(processor.process_block(np.ones((512, 2), np.float32)), .25)
    finally:
        close_window(app, w, c)


def test_remastered_disabled_reasons_and_live_lock_are_specific(app):
    w, c, *_ = window_session(app)
    try:
        assert 'No preparation' in w.cancel_research.toolTip()
        w.state = replace(w.state, file_state=UIState.PLAYING, can_play=True,
                          duration=303.71, file_sample_rate=48000, file_channels=2)
        w.apply_state()
        assert not w.apply_research.isEnabled()
        assert '303.71' in w.apply_research.toolTip()
        assert w.apply_research.accessibleDescription() == w.apply_research.toolTip()
        w.state = replace(w.state, live_active=True, can_play=False)
        w.apply_state()
        assert 'Stop LIVE' in w.research_admission.text()
    finally:
        close_window(app, w, c)


def test_native_volume_clicks_reach_live_callback_pcm_and_single_selected_output(app):
    w, c, backend, *_ = window_session(app)
    gate = threading.Event()
    gate.set()

    class Dry(PassThrough):
        def process_block(self, block):
            assert gate.wait(2)
            return super().process_block(block)

    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        click(app, w, w.start_live)
        c.live.processor.delegate = Dry(48000, 2)
        warmup(c.live)
        signal = np.full((BLOCK, 2), .4, np.float32)

        def output():
            for _ in range(4):
                gate.clear()
                try:
                    pcm = c.live.stream.pump(signal)
                finally:
                    gate.set()
                wait_for(lambda: c.live.output.count == 1 or c.live.halt.is_set())
                assert not c.live.halt.is_set(), c.live.error
            return pcm

        for percent in (100, 50, 25, 0, 100):
            w.monitor_volume.setValue(percent)
            w.research_toggle.setFocus()
            QTest.qWait(160)
            wait_ui(app, lambda: not w.busy and w.state.monitor_volume == percent)
            np.testing.assert_allclose(output(), signal * (percent / 100), atol=1e-7, rtol=0)
            np.testing.assert_array_equal(signal, np.full((BLOCK, 2), .4, np.float32))
        click(app, w, w.mute_volume)
        wait_ui(app, lambda: w.state.monitor_volume == 0)
        assert not np.any(output())
        assert len(backend.streams) == 1
        assert 'native 11' in w.state.live_opened_output
        click(app, w, w.stop_live)
        assert backend.streams[0].closed
    finally:
        gate.set()
        close_window(app, w, c)
