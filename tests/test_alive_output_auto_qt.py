import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtWidgets import QFileDialog

from isla.control import UIState
from test_control import prepared_buffers
from test_device_setup_ux import add_output
from test_qt_window import app, window_session, close_window, wait_ui, click


def load_file(app,w,c,monkeypatch):
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args:('automatic.wav',''))
    click(app,w,w.open_file)
    c.job.result=prepared_buffers(),48000
    wait_ui(app,lambda:w.state.file_state==UIState.READY)


@pytest.mark.parametrize('blackhole',[True,False])
def test_open_and_play_connects_output_syncs_panels_and_locks_setup(app,monkeypatch,blackhole):
    w,c,live,files,devices,routing=window_session(app)
    native,default=routing.snapshot()
    native[0]['alive']=blackhole
    add_output(devices,native,'Sony connected headphones',20)
    routing.snapshot=lambda:(native,default)
    try:
        load_file(app,w,c,monkeypatch)
        click(app,w,w.play)
        assert c.output=='Sony connected headphones'
        assert w.output.currentData()==w.file_output.currentData()==w.state.selected_output
        assert w.state.source=='file' and c.live.config is None and not live.streams
        assert 'Connected: Sony connected headphones'==w.device_status.text()
        assert w.apply_devices.text()=='Connected — ALIVE playing'
        assert not any(control.isEnabled() for control in (
            w.apply_devices,w.auto_setup,w.output,w.file_output,w.rate,w.start_live))
        assert 'Click Stop in ALIVE' in w.next_action.text()
        assert len(files.streams)==1
        click(app,w,w.stop_file)
        assert w.apply_devices.text()==('Connected — ready' if blackhole else 'Use These Devices')
        assert w.start_live.isEnabled() == blackhole
        assert w.output.isEnabled() and w.file_output.isEnabled() and w.auto_setup.isEnabled()
    finally:
        close_window(app,w,c)


def test_ambiguous_play_guides_choice_and_uses_choice_without_an_apply_click(app,monkeypatch):
    w,c,_,files,devices,routing=window_session(app)
    native,default=routing.snapshot()
    for i in range(2):
        add_output(devices,native,f'Headphones {i}',20+i)
    routing.snapshot=lambda:(native,default)
    try:
        load_file(app,w,c,monkeypatch)
        click(app,w,w.play)
        assert 'Several listening devices' in w.file_error.text() and not files.streams
        choice=next(i for i in range(w.file_output.count())
                    if w.file_output.itemData(i) and w.file_output.itemData(i).name=='Headphones 1')
        w.file_output.setCurrentIndex(choice)
        click(app,w,w.play)
        assert w.state.output=='Headphones 1' and len(files.streams)==1
        assert not w.global_error.text() and not w.file_error.text()
    finally:
        close_window(app,w,c)
