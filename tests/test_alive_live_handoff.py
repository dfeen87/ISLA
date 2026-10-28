"""One listening-device choice, with exclusive ALIVE/LIVE stream ownership."""
import numpy as np
import pytest

from isla.control import UIState
from isla.playback import AudioError
from test_alive import PendingPreparation
from test_alive_output_auto import prepared_service
from test_device_setup_ux import add_output
from test_live import BLOCK, wait_for, warmup


@pytest.mark.parametrize('prior_live', [False, True])
def test_alive_stop_to_live_reuses_output_without_another_setup(prior_live):
    service, c, live, files, devices, routing = prepared_service()
    native, _ = routing.snapshot()
    add_output(devices, native, 'Sony headphones', 20)
    routing.snapshot = lambda: (native, 10)
    try:
        if prior_live:
            service.auto_setup_devices()
            service.start_live()
            service.stop_live()
        service.file_command('play')
        original = c.player.buffers['original']
        output = service.selected_output
        assert output.name == 'Sony headphones'
        assert service.rate == 44100
        assert not service.snapshot().live_active
        assert not service.snapshot().can_start
        assert all(stream.closed for stream in live.streams)
        with pytest.raises(AudioError, match='Stop ALIVE'):
            service.start_live()
        service.file_command('stop')
        state = service.snapshot()
        assert state.source == 'file'  # A saved connection isn't a running source.
        assert state.can_start and state.live_state == UIState.LIVE_READY
        assert files.streams[-1].closed
        service.start_live()
        assert c.source == 'system' and c.live.running
        assert service.selected_output == output
        assert c.live.config.output_name == 'Sony headphones'
        assert c.live.config.rate == 44100
        assert c.player.buffers['original'] is original and c.player.stream is None
        assert not c.live.error
        # Pump real monitor/DSP work through the fake hardware at block boundaries.
        warmup(c.live)
        for _ in range(12):
            before = c.live.output._produced
            c.live.stream.pump(np.zeros((BLOCK, 2), np.float32))
            wait_for(lambda: c.live.output._produced > before or c.live.halt.is_set())
            assert not c.live.halt.is_set(), c.live.error
        with pytest.raises(AudioError, match='Stop LIVE'):
            service.file_command('play')
        service.stop_live()
        service.file_command('play')
        assert c.source == 'file' and c.player.stream is not None
        assert all(stream.closed for stream in live.streams)
        assert len(files.streams) == 2
        assert routing.snapshot()[1] == 10
    finally:
        service.shutdown()
        c.close()


@pytest.mark.parametrize('problem', ['missing_capture', 'changed_output', 'wrong_route'])
def test_live_handoff_revalidates_saved_connection_before_open(problem):
    service, c, live, files, _, routing = prepared_service()
    native, _ = routing.snapshot()
    routing.snapshot = lambda: (native, 10)
    try:
        service.file_command('play')
        service.file_command('stop')
        if problem == 'missing_capture':
            native[0]['alive'] = False
        elif problem == 'changed_output':
            native[1]['id'] = 999
        else:
            routing.snapshot = lambda: (native, 11)
        with pytest.raises(AudioError):
            service.start_live()
        assert not live.streams and files.streams[-1].closed
        assert c.source == 'file' and not service.snapshot().live_active
    finally:
        service.shutdown()
        c.close()


def test_handoff_keeps_explicit_live_rate_for_the_same_output():
    service, c, _, _, devices, routing = prepared_service()
    native, _ = routing.snapshot()
    add_output(devices, native, 'Sony headphones', 20)
    routing.snapshot = lambda: (native, 10)
    try:
        service.refresh_devices()
        service.select_devices(service.captures[0], service.outputs[-1], 48000)
        service.file_command('play')
        service.file_command('stop')
        service.start_live()
        assert service.rate == c.live.config.rate == 48000
    finally:
        service.shutdown()
        c.close()


def test_saved_connection_cannot_start_live_during_file_preparation():
    service, c, live, _, _, routing = prepared_service()
    native, _ = routing.snapshot()
    routing.snapshot = lambda: (native, 10)
    try:
        service.file_command('play')
        service.file_command('stop')
        c.job = PendingPreparation('next-song.wav')
        assert not service.snapshot().can_start
        with pytest.raises(AudioError, match='Finish or cancel ALIVE preparation'):
            service.start_live()
        assert not live.streams and c.source == 'file'
    finally:
        service.shutdown()
        c.close()
