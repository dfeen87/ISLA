"""ALIVE Play resolves listening hardware without configuring system capture."""
import pytest

from isla.control import ControlService, UIState
from isla.playback import AudioError
from test_control import make_session, prepared_buffers
from test_device_setup_ux import add_output


def prepared_service():
    controller, live, files, devices, routing = make_session(default=11)
    controller.player.install(prepared_buffers(),48000)
    service = ControlService(controller)
    return service, controller, live, files, devices, routing


@pytest.mark.parametrize('blackhole',[True,False])
def test_play_finds_only_output_without_live_configuration_or_mac_routing(blackhole):
    service,c,live,files,devices,routing=prepared_service()
    native,default=routing.snapshot()
    native[0]['alive']=blackhole
    routing.snapshot=lambda:(native,default)
    checked=[]
    c.player.backend.sd.check_output_settings=lambda **kwargs:checked.append(kwargs)
    try:
        service.file_command('play')
        assert c.output==service.selected_output.name=='Test speakers'
        assert c.source=='file' and c.live.config is None and not live.streams
        assert routing.snapshot()[1]==default
        assert checked==[dict(device=1,samplerate=48000,channels=2,dtype='float32')]
        assert len(files.streams)==1 and service.snapshot().file_state==UIState.PLAYING
        assert 'Connected: Test speakers' in service.snapshot().device_status
        assert not service.snapshot().can_configure
    finally:
        service.shutdown();c.close()


def test_play_prefers_single_external_device_and_reuses_explicit_selection():
    service,c,_,files,devices,routing=prepared_service()
    native,default=routing.snapshot()
    add_output(devices,native,'Sony headphones',20)
    routing.snapshot=lambda:(native,default)
    try:
        service.file_command('play')
        assert c.output=='Sony headphones' and files.streams[0].sr==48000
        service.file_command('stop')
        service.select_file_output(next(d for d in service.outputs if d.name=='Test speakers'))
        service.file_command('play')
        assert c.output=='Test speakers'
        service.file_command('pause')
        position=c.player.position
        service.file_command('play')
        assert c.player.position==position
    finally:
        service.shutdown();c.close()


def test_ambiguous_outputs_require_choice_and_play_accepts_unapplied_choice():
    service,c,live,files,devices,routing=prepared_service()
    native,default=routing.snapshot()
    for i in range(2):
        add_output(devices,native,f'Headphones {i}',20+i)
    routing.snapshot=lambda:(native,default)
    try:
        with pytest.raises(AudioError,match='Several listening devices'):
            service.file_command('play')
        assert not files.streams and c.output is None
        choice=next(d for d in service.outputs if d.name=='Headphones 1')
        service.file_command('play',choice)
        assert c.output=='Headphones 1' and len(files.streams)==1 and not live.streams
    finally:
        service.shutdown();c.close()


def test_output_requirements_fail_before_stream_open_and_preserve_file_state():
    service,c,_,files,_,_=prepared_service()
    original=c.player.buffers['original']
    def unsupported(**kwargs):
        raise RuntimeError('device rate unsupported')
    c.player.backend.sd.check_output_settings=unsupported
    try:
        with pytest.raises(AudioError,match='cannot play this recording at 48,000 Hz'):
            service.file_command('play')
        assert not files.streams and c.output is None
        assert c.player.buffers['original'] is original and c.player.position==0
    finally:
        service.shutdown();c.close()


def test_explicit_device_identity_cannot_silently_change_or_fall_back():
    service,c,_,files,_,routing=prepared_service()
    service.refresh_devices()
    choice=service.outputs[0]
    native,default=routing.snapshot()
    native[1]['id']=999
    routing.snapshot=lambda:(native,default)
    try:
        with pytest.raises(AudioError,match='no longer connected'):
            service.file_command('play',choice)
        assert not files.streams
    finally:
        service.shutdown();c.close()


def test_play_refresh_rebinds_changed_portaudio_index_to_same_native_device():
    service,c,_,files,devices,_=prepared_service()
    service.refresh_devices()
    choice=service.outputs[0]
    devices.insert(0,dict(name='Other virtual device',max_input_channels=0,max_output_channels=2))
    try:
        service.file_command('play',choice)
        assert service.selected_output.native_id==choice.native_id
        assert service.selected_output.index==choice.index+1
        assert c.output=='Test speakers' and len(files.streams)==1
    finally:
        service.shutdown();c.close()


def test_play_never_uses_blackhole_as_the_only_available_file_output():
    service,c,_,files,_,routing=prepared_service()
    native,default=routing.snapshot()
    native[1]['alive']=False
    routing.snapshot=lambda:(native,default)
    try:
        with pytest.raises(AudioError,match='No listening device found'):
            service.file_command('play')
        assert not files.streams and c.output is None
    finally:
        service.shutdown();c.close()


def test_duplicate_play_does_not_rescan_or_reopen_active_output(monkeypatch):
    service,c,_,files,_,_=prepared_service()
    try:
        service.file_command('play')
        monkeypatch.setattr(service,'refresh_devices',lambda:pytest.fail('Active playback must not rescan'))
        service.file_command('play')
        assert len(files.streams)==1 and not files.streams[0].closed
    finally:
        service.shutdown();c.close()


def test_replay_after_eof_rechecks_output_before_opening_a_new_stream():
    service,c,_,files,devices,routing=prepared_service()
    c.player.backend.CallbackStop=files.CallbackStop
    native,default=routing.snapshot()
    try:
        service.file_command('play')
        files.streams[-1].pump(8192)
        assert c.player._ended and c.player.stream is not None
        native[1]['alive']=False
        add_output(devices,native,'New headphones',20)
        routing.snapshot=lambda:(native,default)
        service.file_command('play')
        assert files.streams[0].closed and len(files.streams)==2
        assert c.output=='New headphones' and c.player.position==0
    finally:
        service.shutdown();c.close()


def test_portable_alive_keeps_backend_default_when_coreaudio_is_unavailable(monkeypatch):
    service,c,_,files,_,_=prepared_service()
    c._setup_routing=None
    monkeypatch.setattr('isla.control.sys.platform','linux')
    try:
        service.file_command('play')
        assert len(files.streams)==1 and c.player.output=='Test speakers'
        assert c.source=='file' and c.live.config is None
    finally:
        service.shutdown();c.close()


def test_only_compatible_output_is_selected_without_ambiguous_device_prompt():
    service,c,_,files,devices,routing=prepared_service()
    native,default=routing.snapshot()
    add_output(devices,native,'Unsupported headphones',20)
    add_output(devices,native,'Compatible headphones',21)
    routing.snapshot=lambda:(native,default)
    def check(**kwargs):
        if kwargs['device'] != 4:
            raise RuntimeError('unsupported format')
    c.player.backend.sd.check_output_settings=check
    try:
        service.file_command('play')
        assert c.output=='Compatible headphones' and len(files.streams)==1
    finally:
        service.shutdown();c.close()


def test_existing_output_that_cannot_play_new_format_uses_compatible_fallback():
    service,c,_,files,devices,routing=prepared_service()
    c.output='Test speakers'
    native,default=routing.snapshot()
    add_output(devices,native,'Compatible headphones',20)
    routing.snapshot=lambda:(native,default)
    def check(**kwargs):
        if kwargs['device']==1:
            raise RuntimeError('unsupported format')
    c.player.backend.sd.check_output_settings=check
    try:
        service.file_command('play')
        assert c.output=='Compatible headphones' and len(files.streams)==1
    finally:
        service.shutdown();c.close()
