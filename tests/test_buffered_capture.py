"""Application transport defaults; native reliability is measured separately."""
from types import SimpleNamespace

import pytest

from isla.buffered_capture import (BufferedSystemCaptureBackend,
                                   preferred_capture_rate, preferred_device_rate)
from isla.live import BLOCK
from isla.terminal import TerminalController
from test_live import FakeBackend, fake_routing, mock_playback


@pytest.mark.parametrize('native,expected', [(44100., 44100), (48000., 48000),
                                            (96000., 48000), (None, 48000)])
def test_preferred_rate_accepts_only_supported_device_defaults(native, expected):
    assert preferred_device_rate({'default_samplerate': native}) == expected


@pytest.mark.parametrize('transport,latency', [('bltn', ('low', 'high')), ('blue', 'high'),
                                            ('usb ', 'high')])
def test_buffered_backend_verifies_both_native_stream_handles_and_route(transport, latency):
    playback, _ = mock_playback()
    routing = fake_routing(transport=transport)
    backend = BufferedSystemCaptureBackend(playback, routing)
    config = backend.configure('0', '1', 44100)
    calls = []
    stream = SimpleNamespace(close=lambda: calls.append('closed'))
    playback.sd.Stream = lambda **kwargs: calls.append(kwargs) or stream
    routing.validate_stream = lambda sd, opened, expected: calls.append(('identity', expected, opened))
    original_validate = routing.validate
    routing.validate = lambda *args: calls.append('route') or original_validate(*args)
    assert backend.open(config, 'callback') is stream
    assert calls[0] == dict(device=(0, 1), samplerate=44100, channels=(2, 2),
                           dtype='float32', blocksize=BLOCK, latency=latency, callback='callback')
    assert calls[1:] == [('identity', (10, 11), stream), 'route']


@pytest.mark.parametrize('failure', ['identity', 'route'])
def test_buffered_backend_closes_unstarted_stream_on_validation_failure(failure):
    playback, _ = mock_playback()
    routing = fake_routing()
    backend = BufferedSystemCaptureBackend(playback, routing)
    config = backend.configure('0', '1', 48000)
    closed = []
    playback.sd.Stream = lambda **kwargs: SimpleNamespace(close=lambda: closed.append(True))
    def reject(*args):
        raise RuntimeError('verification failed')
    if failure == 'identity':
        routing.validate_stream = reject
    else:
        routing.validate = reject
    with pytest.raises(RuntimeError, match='verification failed'):
        backend.open(config, 'callback')
    assert closed == [True]


def test_terminal_default_backend_uses_robust_buffering():
    playback, _ = mock_playback()
    controller = TerminalController(playback)
    assert isinstance(controller.live.backend, BufferedSystemCaptureBackend)
    controller.close()


def test_window_imports_verified_output_rate_before_first_live_configuration():
    from isla.control import ControlService
    from test_control import make_session
    controller, _, _, devices, _ = make_session()
    devices[1]['default_samplerate'] = 44100.
    controller.output = 'Test speakers'
    service = ControlService(controller)
    try:
        service.refresh_devices()
        assert service.snapshot().rate == 44100
        assert service.snapshot().selected_output.default_rate == 44100
    finally:
        service.shutdown()
        controller.close()


@pytest.mark.parametrize('explicit,expected', [('', 44100), (' 48000', 48000)])
def test_terminal_matches_output_rate_unless_user_supplies_one(explicit, expected):
    playback, devices = mock_playback()
    devices[1]['default_samplerate'] = 44100.
    backend = FakeBackend()
    controller = TerminalController(playback, live_backend=backend)
    try:
        assert preferred_capture_rate(playback, 'Test speakers') == 44100
        controller.execute('source system')
        controller.execute('output "Test speakers"')
        controller.execute('monitor start' + explicit)
        assert controller.live.config.rate == expected
    finally:
        controller.close()
