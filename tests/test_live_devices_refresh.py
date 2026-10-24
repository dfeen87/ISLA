"""Device population, PortAudio cache refresh, identity leases and lifecycle."""
from types import SimpleNamespace

import pytest

from isla.control import ControlService
from isla.device_refresh import eligible_devices, refresh_portaudio
from isla.playback import AudioError
from test_control import make_session, selected_service


def test_split_bluetooth_names_are_disambiguated_by_direction():
    native = [dict(id=21,name='AirPods',alive=True,input=True,output=False,transport='blue'),
              dict(id=22,name='AirPods',alive=True,input=False,output=True,transport='blue')]
    pa = [dict(index=3,name='AirPods',max_input_channels=1,max_output_channels=0),
          dict(index=4,name='AirPods',max_input_channels=0,max_output_channels=2)]
    captures,outputs = eligible_devices(native,pa)
    assert not captures and len(outputs) == 1
    assert outputs[0]['native_id'] == 22 and outputs[0]['index'] == 4
    native.append(dict(native[1],id=23))
    assert not eligible_devices(native,pa)[1], 'Same-direction ambiguity must fail closed.'


def test_terminal_picker_includes_split_bluetooth_playback_entry():
    c,_,_,devices,routing = make_session()
    entries,default = routing.snapshot()
    entries.extend([dict(id=21,name='AirPods',alive=True,input=True,output=False,transport='blue'),
                    dict(id=22,name='AirPods',alive=True,input=False,output=True,transport='blue')])
    devices.extend([dict(name='AirPods',max_input_channels=1,max_output_channels=0),
                    dict(name='AirPods',max_input_channels=0,max_output_channels=2)])
    routing.snapshot = lambda:(entries,default)
    try:
        captures,outputs = c._audio_setup_devices()
        assert len(captures) == 1
        assert [d['native_id'] for d in outputs if d['name'] == 'AirPods'] == [22]
    finally: c.close()


def test_missing_blackhole_does_not_hide_step_two_outputs_and_initial_retry_recovers():
    c,_,_,devices,routing = make_session()
    original = routing.snapshot
    entries,default = original()
    routing.snapshot = lambda: ([d for d in entries if d['name'] != 'BlackHole 2ch'],default)
    s = ControlService(c)
    try:
        s.refresh_devices()
        assert not s.captures and len(s.outputs) == 1
        assert not s.snapshot().can_start and 'BlackHole' in s.routing_message
        routing.snapshot = original
        s.refresh_devices()
        assert len(s.captures) == 1 and len(s.outputs) == 1
        assert s.selected_capture == s.captures[0]
    finally: s.shutdown(); c.close()


def test_rescan_maps_new_indices_to_same_native_identity_before_first_start(monkeypatch):
    s,c,live,_,devices,_ = selected_service()
    try:
        old = s.selected_output
        def rescan(controller):
            assert controller.live.stream is None and not controller.live.running
            devices.insert(0,dict(name='Unrelated mic',max_input_channels=1,max_output_channels=0))
        monkeypatch.setattr('isla.control.refresh_portaudio',rescan)
        s.start_live()
        assert s.selected_output.native_id == old.native_id
        assert s.selected_output.index == old.index+1
        assert 'LIVE opened' in s.snapshot().device_status
        assert len(live.streams) == 1
        monkeypatch.setattr('isla.control.refresh_portaudio',lambda c: None)
        s.stop_live()
        assert s.devices_need_refresh
        s.refresh_devices()
        assert not s.devices_need_refresh and 'refreshed' in s.device_status
    finally: s.shutdown(); c.close()


def test_replaced_same_name_native_device_is_not_silently_rebound():
    s,c,live,_,_,routing = selected_service()
    try:
        entries,default = routing.snapshot()
        entries[1]['id'] = 111
        routing.snapshot = lambda: (entries,default)
        with pytest.raises(AudioError,match='stale'):
            s.start_live()
        assert not live.streams and not s.snapshot().can_start
    finally: s.shutdown(); c.close()


def test_portaudio_cache_lifetime_refresh_is_idle_only_and_recovers_failed_init(monkeypatch):
    c,*_ = make_session()
    calls = []
    def terminate(): calls.append('terminate'); sd._initialized -= 1
    def initialize(): calls.append('initialize'); sd._initialized += 1
    sd = SimpleNamespace(__name__='sounddevice',_initialized=1,_terminate=terminate,_initialize=initialize)
    c.player.backend.sd = sd
    monkeypatch.setattr('isla.device_refresh.sys.platform','darwin')
    try:
        assert refresh_portaudio(c)
        assert calls == ['terminate','initialize'] and sd._initialized == 1
        c.player.stream = object()
        with pytest.raises(AudioError,match='Stop'): refresh_portaudio(c)
        c.player.stream = None
        assert calls == ['terminate','initialize']
        sd._initialized = 0
        assert refresh_portaudio(c)
        assert calls[-1] == 'initialize' and sd._initialized == 1
    finally: c.player.stream = None; c.close()
