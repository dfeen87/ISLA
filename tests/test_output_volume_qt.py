import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from isla.qt_window import CommandWorker, ControlWindow
from isla.coreaudio import fourcc
from test_control import make_session
from test_output_volume import FakeCoreAudio
from test_qt_window import app, close_window, wait_ui, click


def test_device_slider_reads_real_level_and_changes_it_during_live(app):
    c, live, *_rest, routing = make_session()
    routing.ca = FakeCoreAudio()
    worker = CommandWorker(c)
    w = ControlWindow(worker)
    w.show()
    worker.start()
    try:
        wait_ui(app, lambda: w.state is not None and not w.busy)
        click(app, w, w.auto_setup)
        assert w.device_volume.isEnabled() and w.device_volume.value() == 19
        assert w.device_volume_value.text() == '19%'
        assert not routing.ca.writes  # Startup and all GUI reconciliation are read-only.
        click(app, w, w.start_live)
        stream = c.live.stream
        w.device_volume.setFocus()
        QTest.keyClick(w.device_volume, Qt.Key.Key_Right)
        wait_ui(app, lambda: w.state.output_volume_percent == 20 and w._device_volume_pending is None)
        assert w.device_volume.value() == 20 and w.device_volume_value.text() == '20%'
        assert c.live.stream is stream and len(live.streams) == 1
        assert w.monitor_volume.value() == 50
        assert len(routing.ca.writes) == 1
        # An external hardware edit is displayed without being written back.
        routing.ca.values[11, fourcc('volm')] = .4
        wait_ui(app, lambda: w.device_volume.value() == 40)
        assert len(routing.ca.writes) == 1
    finally:
        close_window(app, w, c)
