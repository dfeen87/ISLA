import pytest
pytest.importorskip('PySide6.QtWidgets')

from isla.control import UIState
from test_alive_output_auto_qt import load_file
from test_device_setup_ux import add_output
from test_qt_window import app, window_session, close_window, click


def test_alive_first_then_live_needs_only_stop_and_start(app, monkeypatch):
    w, c, live, files, devices, routing = window_session(app)
    native, _ = routing.snapshot()
    add_output(devices, native, 'Sony headphones', 20)
    routing.snapshot = lambda: (native, 10)
    try:
        load_file(app, w, c, monkeypatch)
        click(app, w, w.play)
        assert w.apply_devices.text() == 'Connected — ALIVE playing'
        assert w.live_state_indicator.property('monitorState') == 'idle'
        assert not w.state.live_active and not live.streams
        assert w.rate.currentData() == w.state.rate == 44100
        assert not w.start_live.isEnabled()
        assert 'Click Stop in ALIVE' in w.next_action.text()
        click(app, w, w.stop_file)
        assert w.state.source == 'file'
        assert w.state.live_state == UIState.LIVE_READY
        assert w.start_live.isEnabled()
        assert w.apply_devices.text() == 'Connected — ready'
        assert 'Start LIVE' in w.next_action.text()
        click(app, w, w.start_live)
        assert files.streams[-1].closed and len(live.streams) == 1
        assert c.source == 'system' and w.state.live_active
        assert w.apply_devices.text() == 'Connected — LIVE playing'
        assert w.live_state_indicator.property('monitorState') == 'running'
        assert c.live.config.rate == 44100
        click(app, w, w.stop_live)
        click(app, w, w.play)
        assert live.streams[-1].closed and len(files.streams) == 2
        assert w.apply_devices.text() == 'Connected — ALIVE playing'
        assert w.live_state_indicator.property('monitorState') == 'idle'
    finally:
        close_window(app, w, c)
