"""Native volume writes stay on the explicitly selected physical output."""
import ctypes as C
import pytest

from isla.control import ControlService, DeviceChoice
from isla.coreaudio import fourcc
from isla.playback import AudioError
from test_control import make_session


class Call:
    def __init__(self, method):
        self.method = method
    def __call__(self, *args):
        return self.method(*args)


class FakeCoreAudio:
    def __init__(self):
        self.values = {(11, fourcc('volm')): .1875, (11, fourcc('mute')): 0}
        self.readonly = set()
        self.writes = []
        self.AudioObjectHasProperty = Call(self.has)
        self.AudioObjectGetPropertyData = Call(self.get)
        self.AudioObjectIsPropertySettable = Call(self.settable)
        self.AudioObjectSetPropertyData = Call(self.set)

    def has(self, identity, address):
        a = address._obj
        return (identity, a.selector) in self.values and a.scope == fourcc('outp') and a.element == 0

    def get(self, identity, address, _, qualifier, size, value):
        value._obj.value = self.values[identity, address._obj.selector]
        return 0

    def settable(self, identity, address, result):
        result._obj.value = self.has(identity, address) and address._obj.selector not in self.readonly
        return 0

    def set(self, identity, address, _, qualifier, size, value):
        a = address._obj
        self.writes.append((identity, a.selector, a.scope, a.element, value._obj.value))
        self.values[identity, a.selector] = value._obj.value
        return 0


def volume_session():
    c, live, files, devices, routing = make_session()
    routing.ca = FakeCoreAudio()
    service = ControlService(c)
    service.auto_setup_devices()
    return service, c, live, files, routing


def test_discovery_and_unity_digital_volume_do_not_raise_hardware_volume():
    s, c, _, _, routing = volume_session()
    try:
        state = s.snapshot()
        assert state.output_volume_percent == 19 and state.output_volume_available
        s.set_monitor_volume(100)
        s.poll()
        assert s.snapshot().monitor_volume == 100
        assert not routing.ca.writes
    finally:
        s.shutdown(); c.close()


def test_explicit_physical_volume_edit_preserves_stream_digital_gain_and_route():
    s, c, live, _, routing = volume_session()
    try:
        s.start_live()
        stream, worker = c.live.stream, c.live.worker
        s.set_output_volume(s.selected_output, 60)
        assert s.snapshot().output_volume_percent == 60
        assert c.live.stream is stream and c.live.worker is worker and len(live.streams) == 1
        assert c.source == 'system' and routing.snapshot()[1] == 10
        assert s.snapshot().monitor_volume == 50 and s.snapshot().alive_volume == 25
        assert routing.ca.writes == [(11, fourcc('volm'), fourcc('outp'), 0, C.c_float(.6).value)]
    finally:
        s.shutdown(); c.close()


@pytest.mark.parametrize('percent', [-1, 101, True, 1.5])
def test_invalid_volume_cannot_write(percent):
    s, c, _, _, routing = volume_session()
    try:
        with pytest.raises(AudioError, match='whole number'):
            s.set_output_volume(s.selected_output, percent)
        assert not routing.ca.writes
    finally:
        s.shutdown(); c.close()


@pytest.mark.parametrize('defect', ['identity', 'virtual', 'readonly', 'unsupported'])
def test_changed_or_unsupported_device_never_falls_back_to_default_output(defect):
    s, c, _, _, routing = volume_session()
    native, default = routing.snapshot()
    try:
        choice = s.selected_output
        if defect == 'identity':
            native[1]['id'] = 999
        elif defect == 'virtual':
            native[1]['transport'] = 'virt'
        elif defect == 'readonly':
            routing.ca.readonly.add(fourcc('volm'))
        else:
            del routing.ca.values[11, fourcc('volm')]
        routing.snapshot = lambda: (native, default)
        with pytest.raises(AudioError):
            s.set_output_volume(choice, 100)
        assert not routing.ca.writes
        assert not s.snapshot().output_volume_available
    finally:
        s.shutdown(); c.close()


def test_muted_output_is_unmuted_only_after_an_explicit_nonzero_edit():
    s, c, _, _, routing = volume_session()
    try:
        routing.ca.values[11, fourcc('mute')] = 1
        s.refresh_devices(rescan=False)
        assert s.snapshot().output_volume_muted and not routing.ca.writes
        s.set_output_volume(s.selected_output, 30)
        assert not s.snapshot().output_volume_muted
        assert [w[1] for w in routing.ca.writes] == [fourcc('volm'), fourcc('mute')]
    finally:
        s.shutdown(); c.close()


def test_pending_edit_for_previous_output_is_rejected_even_if_it_is_connected():
    s, c, _, _, routing = volume_session()
    try:
        old = s.selected_output
        s.selected_output = DeviceChoice(3, 'Other speakers', 33)
        with pytest.raises(AudioError, match='device changed'):
            s.set_output_volume(old, 100)
        assert not routing.ca.writes
    finally:
        s.shutdown(); c.close()
