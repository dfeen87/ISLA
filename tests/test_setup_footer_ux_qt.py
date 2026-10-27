import numpy as np
import pytest
pytest.importorskip('PySide6.QtWidgets')

from isla.control import UIState
from test_control import prepared_buffers
from test_device_setup_ux import add_output
from test_qt_window import app, window_session, close_window, wait_ui, click


def test_find_connected_devices_chooses_headphones_and_explains_remaining_step(app):
    w, c, backend, _, devices, routing = window_session(app)
    native, _ = routing.snapshot()
    add_output(devices, native, 'Sony connected headphones', 22)
    routing.snapshot = lambda: (native, 11)  # Mac still sends sound to its speakers.
    try:
        click(app, w, w.auto_setup)
        assert c.output == 'Sony connected headphones' and c.source == 'system'
        assert w.output.currentData().name == c.output
        assert w.rate.currentData() == w.state.rate == 44100
        assert not backend.streams
        assert 'Step 2' in w.next_action.text() and 'Check My Setup' in w.next_action.text()
        assert not w.start_live.isEnabled()
        assert w.output.width() > w._live_panel_widget.width()*.7
        routing.snapshot = lambda: (native, 10)
        click(app, w, w.recheck)
        assert 'Ready:' in w.next_action.text() and w.start_live.isEnabled()
        assert not backend.streams  # Discovery/checking never starts playback.
        assert w.wave_signature._status.source == 'LIVE'
        assert w.wave_signature._status.selected == 'bypass'
        assert not w.wave_signature._wave_timer.isActive()
    finally:
        close_window(app, w, c)


def test_alive_footer_changes_only_after_callback_confirms_effect_and_stops_on_pause(app):
    w, c, _, files, *_ = window_session(app)
    try:
        w.submit('load', 'fixture.wav')
        wait_ui(app, lambda: not w.busy)
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        click(app, w, w.play)
        files.streams[-1].pump()
        wait_ui(app, lambda: w.wave_signature._status.applied == 'bypass')
        click(app, w, w.file_modes['velvet'])
        assert w.wave_signature._status.selected == 'velvet'
        assert w.wave_signature._status.stage == 'Switching'
        assert not w.wave_signature._wave_timer.isActive()
        files.streams[-1].pump()
        wait_ui(app, lambda: w.wave_signature._status.stage == 'Playing')
        assert w.wave_signature._status.applied == 'velvet'
        assert w.wave_signature._wave_timer.isActive()
        click(app, w, w.pause)
        assert w.wave_signature._status.stage == 'Paused'
        assert w.wave_signature._status.selected == 'velvet'
        assert not w.wave_signature._wave_timer.isActive()
    finally:
        close_window(app, w, c)
