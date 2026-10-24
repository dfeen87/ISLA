"""GUI coordination without Qt, audio hardware or a macOS desktop."""
from dataclasses import replace
from pathlib import Path
import sys
import threading
import time

import numpy as np
import pytest

from drivers import cli
from isla.control import ControlService, UIState
from isla.playback import AudioError
from isla.terminal import TerminalController
from test_alive import FakeBackend as FileBackend, PendingPreparation
from test_live import FakeBackend as LiveBackend, fake_routing, mock_playback


def make_session(default=10):
    playback, devices = mock_playback()
    files = FileBackend()
    playback.open = files.open
    playback.output_name = lambda: playback.output_device or 'Test speakers'
    routing = fake_routing(default=default)
    live = LiveBackend()
    c = TerminalController(playback, PendingPreparation, live_backend=live, routing=routing)
    c.live._monotonic_clock = lambda: 0.0  # Manually driven fake, no real callbacks.
    return c, live, files, devices, routing


def prepared_buffers():
    return {mode: np.full((8192, 2), i / 10, np.float32)
            for i, mode in enumerate(('original', 'velvet', 'legato', 'melt'))}


def selected_service(default=10):
    c, live, files, devices, routing = make_session(default)
    service = ControlService(c)
    service.refresh_devices()
    service.select_devices(service.captures[0], service.outputs[0])
    return service, c, live, files, devices, routing


def test_no_file_loading_ready_play_pause_stop_exact_original():
    c, _, files, _, _ = make_session()
    s = ControlService(c)
    try:
        state = s.poll()
        assert state.file_state == UIState.NO_FILE
        assert not state.can_play and 'Open an audio file' in state.preparation
        s.load_file('a piano.wav')
        assert s.poll().file_state == UIState.PREPARING
        assert not s.snapshot().can_play
        c.job.result = prepared_buffers(), 48000
        assert s.poll().file_state == UIState.READY
        assert s.snapshot().can_play
        s.file_command('play')
        assert s.snapshot().file_state == UIState.PLAYING
        for mode in ('velvet', 'legato', 'melt', 'original'):
            s.file_command('bypass' if mode == 'original' else 'mode ' + mode)
            assert c.player._selected is c.player.buffers[mode]
        assert len(files.streams) == 1
        s.file_command('pause')
        assert s.snapshot().file_state == UIState.PAUSED
        s.file_command('play')
        s.file_command('stop')
        assert s.snapshot().file_state == UIState.STOPPED
    finally:
        s.shutdown()
        c.close()
    assert all(stream.closed for stream in files.streams)


def test_recoverable_preparation_failure_can_reload_and_close_pending_job():
    c, *_ = make_session()
    s = ControlService(c)
    s.load_file('bad.wav')
    job = c.job
    def fail():
        raise ValueError('preparation process died')
    job.poll = fail
    with pytest.raises(ValueError, match='process died'):
        s.poll()
    assert job.closed and c.job is None
    s.load_file('good.wav')
    pending = c.job
    s.shutdown()
    assert pending.closed and c.job is None and not c.closed
    assert c.execute('help')
    c.close()


def test_routing_mismatch_has_current_required_and_distinct_listening_output():
    s, c, live, *_ = selected_service(default=11)
    try:
        state = s.snapshot()
        assert state.system_output == 'Test speakers'
        assert state.output == 'Test speakers'
        assert not state.can_start and state.live_state == UIState.ROUTING_INVALID
        assert "Output to BlackHole 2ch" in state.routing_message
        assert "Keep 'Test speakers' as the physical output selected inside ISLA" in state.routing_message
        with pytest.raises(AudioError, match='Single-path'):
            s.start_live()
        assert not live.streams
    finally:
        s.shutdown()
        c.close()


def test_start_independently_rechecks_route_and_native_identity_after_ready():
    s, c, live, _, _, routing = selected_service()
    try:
        assert s.snapshot().can_start
        routing.snapshot = fake_routing(default=11).snapshot
        with pytest.raises(AudioError, match='Single-path'):
            s.start_live()
        assert not live.streams
        routing.snapshot = fake_routing().snapshot
        s.refresh_devices()
        assert s.snapshot().can_start
        original = routing.snapshot
        entries, default = original()
        entries[1]['id'] = 111
        routing.snapshot = lambda: (entries, default)
        with pytest.raises(AudioError, match='stale|identity'):
            s.start_live()
        assert not live.streams
        assert not s.snapshot().can_start
    finally:
        s.shutdown()
        c.close()


def test_live_start_stop_mode_duplicate_conflict_and_cleanup():
    s, c, live, files, *_ = selected_service()
    try:
        s.live_mode('bypass')
        assert 'active' in s.start_live().lower()
        assert s.snapshot().live_state == UIState.LIVE_RUNNING
        with pytest.raises(AudioError, match='already'):
            s.start_live()
        with pytest.raises(AudioError, match='Stop'):
            s.load_file('bad.wav')
        with pytest.raises(AudioError, match='Stop'):
            s.file_command('play')
        with pytest.raises(AudioError, match='Stop'):
            s.select_devices(s.captures[0], s.outputs[0])
        for mode in ('velvet', 'legato', 'melt', 'bypass'):
            s.live_mode(mode)
            assert c.live.mode == mode
            assert s.snapshot().live_mode == mode
        assert len(live.streams) == 1 and not files.streams
        s.stop_live()
        assert not s.snapshot().live_active and live.streams[0].closed
    finally:
        s.shutdown()
        c.close()



def test_gui_live_start_defaults_original_and_monitor_volume_is_bounded():
    s, c, backend, _, _, _ = selected_service()
    try:
        s.live_mode('melt')  # configured before starting
        assert s.snapshot().live_mode == 'melt'
        s.set_monitor_volume(35)
        assert s.snapshot().monitor_volume == 35
        with pytest.raises(ValueError, match='0 to 100'):
            s.set_monitor_volume(101)
        with pytest.raises(ValueError, match='0 to 100'):
            s.set_monitor_volume(-1)
        with pytest.raises(ValueError, match='0 to 100'):
            s.set_monitor_volume(0.5)
        s.start_live()
        assert c.live.mode == 'bypass'
        assert s.snapshot().monitor_volume == 35
        assert len(backend.streams) == 1
        for mode in ('velvet', 'legato', 'melt', 'bypass'):
            s.live_mode(mode)
            assert s.snapshot().live_mode == mode
            assert len(backend.streams) == 1
        s.set_monitor_volume(0)
        assert s.snapshot().monitor_volume == 0
        s.set_monitor_volume(100)
        assert s.snapshot().monitor_volume == 100
        s.stop_live()
        assert backend.streams[0].closed
    finally:
        s.shutdown()
        c.close()


@pytest.mark.parametrize('change', ['missing_blackhole', 'unplug_output', 'rename_output', 'reindex', 'aggregate', 'ambiguous'])
def test_device_refresh_and_start_fail_closed(change):
    s, c, live, _, devices, routing = selected_service()
    try:
        entries, default = routing.snapshot()
        if change == 'missing_blackhole':
            entries.pop(0)
        elif change == 'unplug_output':
            entries[1]['alive'] = False
        elif change == 'rename_output':
            entries[1]['name'] = 'Other speakers'
        elif change == 'reindex':
            devices.insert(0, dict(name='New microphone', max_input_channels=1, max_output_channels=0))
        elif change == 'aggregate':
            entries[1]['transport'] = 'grup'
        else:
            devices.append(dict(devices[1]))
        routing.snapshot = lambda: (entries, default)
        s.refresh_devices()
        assert not s.snapshot().can_start
        with pytest.raises(AudioError):
            s.start_live()
        assert not live.streams
    finally:
        s.shutdown()
        c.close()


def test_refresh_filters_virtual_and_unsupported_physical_outputs():
    c, _, _, devices, routing = make_session()
    entries, default = routing.snapshot()
    for name, transport, channels in [('Virtual', 'virt', 2), ('Aggregate', 'grup', 2), ('Mono', 'usb ', 1)]:
        devices.append(dict(name=name, max_input_channels=0, max_output_channels=channels))
        entries.append(dict(id=len(entries) + 20, name=name, transport=transport, alive=True, input=False, output=True))
    routing.snapshot = lambda: (entries, default)
    s = ControlService(c)
    s.refresh_devices()
    assert [d.name for d in s.outputs] == ['Test speakers']
    s.shutdown()
    c.close()


def test_active_file_handoff_preserves_stream_and_returns_usable_terminal():
    c, _, files, *_ = make_session()
    c.player.install(prepared_buffers(), 48000)
    c.player.play()
    stream = c.player.stream
    s = ControlService(c)
    with pytest.raises(AudioError, match='already owns'):
        ControlService(c)
    assert s.poll().file_state == UIState.PLAYING
    assert c.player.stream is stream and len(files.streams) == 1
    s.shutdown()
    assert stream.closed and not c.closed and c.player.buffers
    assert 'Playing' in c.execute('play')
    c.close()


def test_active_live_handoff_does_not_start_another_engine():
    s, c, live, *_ = selected_service()
    s.start_live()
    stream = c.live.stream
    # Release just the test lease to model an already-running CLI session.
    c._window_owner = c._window_thread = None
    borrowed = ControlService(c)
    try:
        borrowed.refresh_devices()
        assert borrowed.snapshot().live_active
        assert c.live.stream is stream and len(live.streams) == 1
    finally:
        borrowed.shutdown()
        c.close()
    assert stream.closed


def test_foreign_thread_and_terminal_cannot_compete_with_window():
    c, *_ = make_session()
    s = ControlService(c)
    s.poll()
    errors = []
    def compete():
        for action in (lambda: s.file_command('play'), lambda: c.execute('play')):
            try:
                action()
            except (AudioError, ValueError) as exc:
                errors.append(str(exc))
    t = threading.Thread(target=compete)
    t.start()
    t.join(timeout=2)
    assert len(errors) == 2 and all('own' in e for e in errors)
    s.shutdown()
    c.close()


def test_shutdown_failure_retains_lease_and_retry_releases(monkeypatch):
    s, c, *_ = selected_service()
    stop = c.live.stop
    monkeypatch.setattr(c.live, 'stop', lambda: (_ for _ in ()).throw(AudioError('worker still stopping')))
    with pytest.raises(AudioError, match='still stopping'):
        s.shutdown()
    assert c._window_owner is s and not s.closed
    monkeypatch.setattr(c.live, 'stop', stop)
    s.shutdown()
    assert c._window_owner is None and c._window_thread is None
    c.close()


def test_launch_dispatch_and_terminal_handoff_and_wizard_refusal(monkeypatch):
    seen = []
    monkeypatch.setattr('isla.window.run_window', lambda controller=None: seen.append(controller) or 0)
    assert cli.main(['window']) == 0
    c, *_ = make_session()
    assert 'Terminal ready' in c.execute('window')
    assert seen == [None, c]
    c.execute('setup audio')
    with pytest.raises(ValueError, match='cancel'):
        c.execute('window')
    c.close()


def test_missing_qt_diagnostic_preserves_cli_and_existing_session(monkeypatch, capsys):
    import builtins
    from isla.window import run_window
    original = builtins.__import__
    def blocked(name, *args, **kw):
        if name == 'isla.qt_window':
            raise ImportError('PySide6 not installed')
        return original(name, *args, **kw)
    c, *_ = make_session()
    monkeypatch.setattr(builtins, '__import__', blocked)
    assert run_window(c) == 1
    assert ".[gui]" in capsys.readouterr().err
    assert getattr(c, '_window_owner', None) is None
    assert c.execute('help')
    c.close()
