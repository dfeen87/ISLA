"""Reproduce operator startup gestures without changing capture fault guards."""
from types import SimpleNamespace

import numpy as np
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from isla.control import UIState
from test_qt_window import app, window_session, close_window, wait_ui, click
from test_live import BLOCK, PassThrough, wait_for, warmup


def test_gui_suggests_new_output_rate_and_keeps_explicit_rate_across_polls(app):
    w, c, _, _, devices, routing = window_session(app)
    try:
        devices[1]['default_samplerate'] = 44100.
        click(app, w, w.refresh)
        w.output.setCurrentIndex(1)
        assert w.rate.currentData() == 44100
        for _ in range(3):
            w.drain_events()
        assert w.rate.currentData() == 44100
        w.rate.setFocus()
        QTest.keyClick(w.rate, Qt.Key.Key_End)
        assert w.rate.currentData() == 48000
        w.output.setCurrentIndex(0)
        w.output.setCurrentIndex(1)
        for _ in range(3):
            w.drain_events()
        assert w.rate.currentData() == 48000
        click(app, w, w.apply_devices)
        assert w.state.rate == 48000
    finally:
        close_window(app, w, c)


def test_live_start_consumes_visible_mute_before_creating_processor(app):
    w, c, backend, *_ = window_session(app)
    try:
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        w.monitor_volume.setValue(0)
        w.volume_timer.stop()  # Deterministic same-tick Start before debounce.
        click(app, w, w.start_live)
        assert w.state.monitor_volume == 0
        assert c.live.processor._applied == 0
        c.live.processor.delegate = PassThrough(48000, 2)
        np.testing.assert_array_equal(
            c.live.processor.process_block(np.ones((BLOCK, 2), np.float32)), 0)
        assert len(backend.streams) == 1
    finally:
        close_window(app, w, c)


def test_rate_edit_cannot_start_previous_configuration_before_next_poll(app):
    w, c, backend, *_ = window_session(app)
    try:
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        assert w.start_live.isEnabled()
        w.rate.setCurrentIndex(w.rate.findData(44100))
        assert not w.submit('start')
        assert not backend.streams
        assert not w.start_live.isEnabled()
        assert w.apply_devices.isEnabled()
        click(app, w, w.apply_devices)
        click(app, w, w.start_live)
        assert c.live.config.rate == 44100
    finally:
        close_window(app, w, c)


def test_repeated_capture_error_has_retry_guidance_without_automatic_restart(app):
    w, c, backend, *_ = window_session(app)
    try:
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        click(app, w, w.start_live)
        warmup(c.live)
        gap = SimpleNamespace(input_overflow=True)
        zeros = np.zeros((BLOCK, 2), np.float32)
        c.live.stream.pump(zeros, gap)
        wait_for(lambda: c.live._recovery_ready or c.live.halt.is_set())
        c.live.stream.pump(zeros, gap)
        wait_ui(app, lambda: not w.state.live_active)
        reason = c.live.error
        assert 'Repeated capture discontinuity' in reason
        assert w.live_state_indicator.property('monitorState') == 'failed'
        assert 'Check My Setup' in w.next_action.text()
        assert 'Start LIVE' in w.live_state_indicator.text()
        assert '..' not in w.live_state_indicator.text()
        assert reason in w.live_health.toPlainText()
        assert len(backend.streams) == 1 and backend.streams[0].closed
        click(app, w, w.recheck)
        assert w.start_live.isEnabled()
        assert len(backend.streams) == 1
        click(app, w, w.start_live)
        assert w.state.live_state == UIState.LIVE_RUNNING
        assert not w.state.live_failure_reason
        assert w.live_state_indicator.property('monitorState') == 'running'
        assert 'has stopped' not in w.next_action.text()
        assert len(backend.streams) == 2
    finally:
        close_window(app, w, c)
