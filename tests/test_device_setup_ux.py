import pytest

from isla.control import ControlService
from isla.playback import AudioError
from test_control import make_session


def add_output(devices, native, name, identity, transport='blue'):
    devices.append(dict(name=name, max_input_channels=0, max_output_channels=2,
                        default_samplerate=44100.))
    native.append(dict(id=identity, name=name, transport=transport,
                       alive=True, input=False, output=True))


@pytest.mark.parametrize('external_count', [0, 1, 2])
def test_auto_setup_selects_only_an_unambiguous_path(external_count):
    controller, backend, _, devices, routing = make_session()
    native, default = routing.snapshot()
    for i in range(external_count):
        add_output(devices, native, f'Headphones {i}', 20+i)
    routing.snapshot = lambda: (native, default)
    service = ControlService(controller)
    try:
        if external_count > 1:
            with pytest.raises(AudioError, match='Several listening devices'):
                service.auto_setup_devices()
            assert controller.output is None and controller.source == 'file'
        else:
            result = service.auto_setup_devices()
            assert 'Found and selected' in result
            assert controller.output == ('Headphones 0' if external_count else 'Test speakers')
            assert service.rate == (44100 if external_count else 48000)
            assert controller.source == 'system'
        assert not backend.streams and not controller.live.running
    finally:
        service.shutdown()
        controller.close()


def test_auto_setup_preserves_an_explicit_existing_output_and_rejects_active_changes():
    controller, backend, _, devices, routing = make_session()
    native, default = routing.snapshot()
    add_output(devices, native, 'Headphones', 20)
    routing.snapshot = lambda: (native, default)
    controller.output = 'Test speakers'
    service = ControlService(controller)
    try:
        service.auto_setup_devices()
        assert controller.output == 'Test speakers'
        service.start_live()
        with pytest.raises(AudioError, match='Stop ALIVE and LIVE'):
            service.auto_setup_devices()
        assert controller.live.running and len(backend.streams) == 1
    finally:
        service.shutdown()
        controller.close()


def test_auto_setup_missing_blackhole_preserves_system_routing_and_offers_correction():
    controller, backend, _, _, routing = make_session()
    native, default = routing.snapshot()
    native[0]['alive'] = False
    routing.snapshot = lambda: (native, default)
    service = ControlService(controller)
    try:
        with pytest.raises(AudioError, match='BlackHole 2ch is not available'):
            service.auto_setup_devices()
        assert routing.snapshot()[1] == default
        assert not backend.streams and controller.source == 'file'
    finally:
        service.shutdown()
        controller.close()
