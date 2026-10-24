"""Actual native Qt controls drive the LIVE worker; no hardware/audio claim."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import threading

import numpy as np
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from isla.streaming import StreamingDSP
from test_qt_window import app,click,close_window,choose_live_mode,wait_ui,window_session
from test_live import wait_for
from tools.remastered_verify import fixture


def test_live_engine_and_depth_widgets_reach_real_dsp_worker(app,monkeypatch):
    gate = threading.Event(); gate.set()
    original = StreamingDSP.process_block
    def scheduled(self,block):
        assert gate.wait(5)
        return original(self,block)
    monkeypatch.setattr(StreamingDSP,'process_block',scheduled)
    w,c,live,_,_,_ = window_session(app)
    try:
        w.capture.setCurrentIndex(1); w.output.setCurrentIndex(1)
        wait_ui(app,lambda:w.apply_devices.isEnabled())
        click(app,w,w.apply_devices)
        assert w.live_engine.isEnabled()
        w.live_engine.setFocus(); QTest.keyClick(w.live_engine,Qt.Key.Key_End)
        wait_ui(app,lambda:not w.busy and w.state.live_engine == 'remastered')
        w.live_intensity.setFocus(); QTest.keyClick(w.live_intensity,Qt.Key.Key_Home)
        for _ in range(10): QTest.keyClick(w.live_intensity,Qt.Key.Key_Right)
        click(app,w,w.apply_live_intensity)
        click(app,w,w.start_live)
        assert 'LIVE opened' in w.device_status.text()
        choose_live_mode(app,w,'melt')
        stream = live.streams[-1]
        for _ in range(8): stream.pump(np.zeros((512,2),np.float32))
        x = fixture(48000,2)
        for block in x[:512*20].reshape(-1,512,2):
            gate.clear()
            try: stream.pump(block)
            finally: gate.set()
            wait_for(lambda:c.live.output.count == 1 or c.live.halt.is_set(),timeout=5)
            assert not c.live.halt.is_set(),c.live.error
        wait_ui(app,lambda:w.state.live_applied_engine == 'remastered')
        assert c.live.processor.delegate.research.intensity == 50
        assert '50%' in w.live_processing_status.text()
        assert len(live.streams) == 1 and c.live.stream is stream
        click(app,w,w.stop_live)
    finally:
        gate.set(); close_window(app,w,c)


def test_stop_automatically_refreshes_new_bluetooth_output_without_blocking_audio(app,monkeypatch):
    w,c,live,_,devices,routing = window_session(app)
    scans = []
    monkeypatch.setattr('isla.control.refresh_portaudio',lambda controller: scans.append(
        (controller.live.running,controller.live.stream is not None)))
    try:
        w.capture.setCurrentIndex(1);w.output.setCurrentIndex(1)
        wait_ui(app,lambda:w.apply_devices.isEnabled())
        click(app,w,w.apply_devices);click(app,w,w.start_live)
        scans.clear()
        entries,default = routing.snapshot()
        entries.extend([dict(id=21,name='AirPods',transport='blue',alive=True,input=True,output=False),
                        dict(id=22,name='AirPods',transport='blue',alive=True,input=False,output=True)])
        routing.snapshot = lambda:(entries,default)
        devices.extend([dict(name='AirPods',max_input_channels=1,max_output_channels=0),
                        dict(name='AirPods',max_input_channels=0,max_output_channels=2)])
        c.live._monotonic_clock = lambda:0.
        w.worker._last_device_refresh = 0.
        wait_ui(app,lambda:w.worker._last_device_refresh != 0.)
        assert not scans, 'Never reset PortAudio while LIVE runs.'
        click(app,w,w.stop_live)
        assert not c.live.running and live.streams[-1].closed
        wait_ui(app,lambda:any(d.name == 'AirPods' for d in w.state.outputs))
        assert scans and not any(running or opened for running,opened in scans)
        assert any(w.output.itemText(i) == 'AirPods (Bluetooth)' for i in range(w.output.count()))
        assert w.state.selected_output.name == 'Test speakers', 'Refresh must not change the listening choice.'
    finally: close_window(app,w,c)
