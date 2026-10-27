"""Real Qt widget tests, offscreen; not native macOS/audio acceptance."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from isla.control import UIState
from isla.qt_window import (CommandWorker, ControlWindow, alive_next_step,
                            audio_diagnostics, remastered_readiness, open_sound_settings)
from test_alive import PendingPreparation
from test_control import make_session, prepared_buffers


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def wait_ui(app, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail('Window operation did not complete')
        time.sleep(.005)
    app.processEvents()


def window_session(app):
    c, live, files, devices, routing = make_session()
    worker = CommandWorker(c)
    w = ControlWindow(worker)
    w.show()
    worker.start()
    wait_ui(app, lambda: w.state is not None and not w.busy)
    return w, c, live, files, devices, routing


def close_window(app, w, c):
    w.close()
    wait_ui(app, lambda: w.closed_cleanly)
    w.worker.thread.join(timeout=2)
    assert not w.worker.thread.is_alive()
    assert not c.closed and c._window_owner is None
    c.close()


def click(app, w, button):
    assert button.isEnabled(), button.text()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_ui(app, lambda: not w.busy)


def activate_live_mode(app, window, mode):
    """Open by mouse and select with native popup keys, never emit signals."""
    combo = window.live_mode_choice
    index = combo.findData(mode)
    assert index >= 0 and combo.isEnabled()
    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    assert combo.view().isVisible()
    app.processEvents()  # Let the native popup lay out before hit-testing.
    QTest.keyClick(combo.view(), Qt.Key.Key_Home)
    for _ in range(index):
        QTest.keyClick(combo.view(), Qt.Key.Key_Down)
    QTest.keyClick(combo.view(), Qt.Key.Key_Return)



def choose_live_mode(app, window, mode):
    activate_live_mode(app, window, mode)
    wait_ui(app, lambda: not window.busy)


def test_widgets_disable_unprepared_controls_and_real_file_lifecycle(app, monkeypatch):
    w, c, live, files, *_ = window_session(app)
    try:
        assert w.windowTitle() == 'ISLA — Audio Control Center'
        assert w.file_status.text() == 'Open an audio file to begin'
        assert 'Open Audio File' in w.file_next_step.text()
        assert 'Initial ALIVE level: 25%' in w.alive_volume_notice.text()
        assert w.alive_volume.value() == 25 and w.monitor_volume.value() == 50
        assert not w.play.isEnabled() and not w.pause.isEnabled()
        assert not any(b.isEnabled() for b in w.file_modes.values())
        assert not w.start_live.isEnabled()
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('piano with spaces.wav', ''))
        click(app, w, w.open_file)
        assert w.state.file_state == UIState.PREPARING
        assert 'Preparing Original' in w.file_next_step.text()
        assert not w.play.isEnabled()
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        assert 'ALIVE is ready' in w.file_next_step.text()
        click(app, w, w.play)
        assert c.player.backend.output_level_percent == 25
        assert w.state.file_state == UIState.PLAYING and w.pause.isEnabled()
        assert 'ALIVE is playing' in w.file_next_step.text()
        assert not w.open_file.isEnabled() and not w.output.isEnabled()
        click(app, w, w.file_modes['melt'])
        assert c.player.mode == 'melt' and len(files.streams) == 1
        import numpy as np
        np.testing.assert_allclose(files.streams[0].pump()[-64:],
                                   np.full((64, 2), .075), atol=1e-7)
        click(app, w, w.file_modes['bypass'])
        assert c.player._selected is c.player.buffers['original']
        click(app, w, w.pause)
        assert w.state.file_state == UIState.PAUSED
        click(app, w, w.stop_file)
        assert w.state.position == 0
    finally:
        close_window(app, w, c)
    assert all(stream.closed for stream in files.streams)





def test_alive_mode_button_mouse_press_survives_50ms_status_polls(app, monkeypatch):
    """A held ALIVE click survives Qt refreshes and switches the playing mode."""
    w, c, live, files, *_ = window_session(app)
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName',
                            lambda *args: ('long prepared recording.m4a', ''))
        click(app, w, w.open_file)
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        click(app, w, w.play)
        assert w.state.file_state == UIState.PLAYING
        assert w.file_modes['bypass'].isChecked()

        # Simulate a real click spanning one or more of the 50 ms UI polls.
        # Previously apply_state disabled/re-enabled every ALIVE mode, which
        # discarded the mouse-down event before Qt could emit clicked.
        for mode in ('velvet', 'legato', 'melt', 'bypass'):
            button = w.file_modes[mode]
            assert button.isEnabled()
            QTest.mousePress(button, Qt.MouseButton.LeftButton)
            assert button.isDown()
            for _ in range(3):
                w.drain_events()
                app.processEvents()
                assert button.isEnabled()
                assert button.isDown(), 'Status refresh canceled an in-flight ALIVE click'
            QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
            expected = 'original' if mode == 'bypass' else mode
            wait_ui(app, lambda: not w.busy and
                    w.state is not None and w.state.file_mode == expected)
            assert c.player.mode == expected
            assert c.player._selected is c.player.buffers[expected]
            assert button.isChecked()
            assert w.state.file_state == UIState.PLAYING
        assert len(files.streams) == 1  # Mode switches must not restart audio.
    finally:
        close_window(app, w, c)


def test_alive_next_step_explains_live_lock_and_restores_file_controls(app, monkeypatch):
    """A stopped, fully prepared ALIVE file must explain why LIVE owns output."""
    w, c, live, files, *_ = window_session(app)
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName',
                            lambda *args: ('My purchased song.m4a', ''))
        click(app, w, w.open_file)
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        click(app, w, w.play)
        click(app, w, w.stop_file)
        assert w.state.file_state == UIState.STOPPED

        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        click(app, w, w.start_live)
        assert w.state.live_active
        assert w.file_status.text() == 'File stopped'
        assert not w.play.isEnabled()
        assert not w.open_file.isEnabled()
        assert not any(button.isEnabled() for button in w.file_modes.values())
        hint = w.file_next_step.text()
        assert 'ALIVE is locked' in hint
        assert 'Stop LIVE' in hint
        assert 'Play' in hint

        click(app, w, w.stop_live)
        wait_ui(app, lambda: not w.state.live_active and w.play.isEnabled())
        assert 'ALIVE is ready' in w.file_next_step.text()
        assert all(button.isEnabled() for button in w.file_modes.values())
        click(app, w, w.play)
        click(app, w, w.file_modes['velvet'])
        assert c.player.mode == 'velvet'
    finally:
        close_window(app, w, c)


def test_alive_next_step_explains_long_song_without_disabling_standard_playback(app):
    """A full-length M4A can play, but the ALIVE research excerpt limit is separate."""
    w, c, *_ = window_session(app)
    try:
        standard = replace(w.state, file_state=UIState.READY, can_play=True,
                           duration=231.33)
        assert 'ALIVE is ready' in alive_next_step(standard)
        w.state = standard
        w.apply_state()
        assert '231.33-second' in w.file_next_step.text()
        assert '30-second research limit' in w.file_next_step.text()
        assert 'Standard ALIVE playback' in w.file_next_step.text()
        assert 'LIVE Remastered' in w.file_next_step.text()

        locked = replace(standard, live_active=True, can_play=False)
        assert 'Stop LIVE' in alive_next_step(locked)
        assert '30-second research limit' in alive_next_step(locked)
        preparing = replace(standard, file_state=UIState.PREPARING,
                            duration=0, can_play=False)
        assert 'Preparing Original' in alive_next_step(preparing)
        failed = replace(standard, file_state=UIState.RECOVERABLE_ERROR,
                         duration=0, can_play=False)
        assert 'Read the error' in alive_next_step(failed)
        assert 'audio operation is in progress' in alive_next_step(standard, busy='load')
    finally:
        close_window(app, w, c)



def test_remastered_preflight_blocks_full_songs_but_keeps_production_modes(app):
    """303-second M4A cannot enter the 30-second research renderer from the GUI."""
    w, c, *_ = window_session(app)
    try:
        # The source file is loaded and regular ALIVE playback remains usable.
        long_song = replace(w.state, file_state=UIState.PLAYING, can_play=True,
                            duration=303.71, file_sample_rate=48000, file_channels=2,
                            file_mode='legato')
        admitted, note = remastered_readiness(long_song)
        assert not admitted and '30-second' in note
        w.state = long_song
        w.apply_state()
        assert not w.apply_research.isEnabled()
        assert not w.cancel_research.isEnabled()
        assert not w.try_remastered_first.isEnabled()
        assert '30-second' in w.try_remastered_first.toolTip()
        assert w.file_modes['velvet'].isEnabled()
        assert '303.71-second' in w.research_admission.text()
        assert 'Remastered availability' in w.health.toPlainText()
        assert 'Legato' in w.health.toPlainText() or 'legato' in w.health.toPlainText()

        # Eligibility is independent from the conventional ALIVE transport.
        good = replace(long_song, duration=12.0, file_sample_rate=48000)
        assert remastered_readiness(good)[0]
        w.state = good
        w.apply_state()
        assert w.enter_research.isEnabled() and w.try_remastered_first.isEnabled()
        assert not w.apply_research.isEnabled()
        assert 'Eligible local excerpt' in w.research_admission.text()
        assert 'Try Remastered First' in w.research_admission.text()

        bad_rate = replace(good, file_sample_rate=32000)
        assert not remastered_readiness(bad_rate)[0]
        w.state = bad_rate
        w.apply_state()
        assert not w.apply_research.isEnabled()
        assert not w.try_remastered_first.isEnabled()
        assert w.file_modes['melt'].isEnabled()
    finally:
        close_window(app, w, c)


def test_remastered_preparation_indicator_and_unified_diagnostics(app):
    """The loading bar is indeterminate and reports active vs requested safely."""
    w, c, *_ = window_session(app)
    try:
        current = replace(w.state, file_state=UIState.PLAYING, can_play=True,
                          duration=12.0, file_sample_rate=44100, file_channels=2,
                          file_mode='legato', research_pending=True, research_workspace=True,
                          research_status='Rendering Velvet in a separate process…',
                          research_active=False)
        w.state = current
        w.apply_state()
        assert w.research_progress.minimum() == 0
        assert w.research_progress.maximum() == 0
        assert not w.apply_research.isEnabled()
        assert w.cancel_research.isEnabled()
        assert 'Now playing: Legato' in w.research_status.text()
        assert 'Preparing separately' in w.research_status.text()
        assert 'NOT YET APPLIED' in w.health.toPlainText()
        assert 'Rendering Velvet' in w.health.toPlainText()
        assert 'Existing playback continues' in w.health.toPlainText()

        applied = replace(current, research_pending=False,
                          file_mode='remastered_velvet',
                          research_active=True, research_mode='velvet',
                          research_intensity=60,
                          research_summary='verified peak 0.42; vetoed 15 frames')
        w.state = applied
        w.apply_state()
        assert w.research_progress.maximum() == 1
        assert not w.research_progress.isVisible()
        assert 'Remastered — 60%' in w.research_status.text()
        assert 'verified peak 0.42' in w.health.toPlainText()
        assert w.apply_research.isEnabled()
        assert w.return_research.isEnabled()
        assert not w.cancel_research.isEnabled()

        canceled = replace(current, research_pending=False,
                           research_status='Research preparation canceled; active audio preserved.')
        assert 'Last preparation: Research preparation canceled' in audio_diagnostics(canceled)
    finally:
        close_window(app, w, c)


def test_file_picker_accepts_purchased_m4a_with_spaces(app, monkeypatch):
    w, c, live, files, *_ = window_session(app)
    try:
        def choose(*args):
            assert args[1] == 'Open audio file'
            assert all(pattern in args[3] for pattern in ('*.wav', '*.m4a', '*.M4A', '*.aac'))
            return 'Purchased music/Piano café.m4a', ''

        monkeypatch.setattr(QFileDialog, 'getOpenFileName', choose)
        assert w.open_file.text() == 'Open Audio File…'
        click(app, w, w.open_file)
        assert str(c.job.path) == 'Purchased music/Piano café.m4a'
        c.job.result = prepared_buffers(), 44100
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        click(app, w, w.play)
        assert w.state.file_state == UIState.PLAYING
    finally:
        close_window(app, w, c)
    assert all(stream.closed for stream in files.streams)


def test_mouse_guided_devices_mismatch_recheck_start_stop_and_modes(app):
    w, c, live, _, _, routing = window_session(app)
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        w.rate.setCurrentIndex(0)
        routing.snapshot = __import__('test_live').fake_routing(default=11).snapshot
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        assert c.source == 'system' and w.state.rate == 44100
        assert not w.start_live.isEnabled()
        assert 'Current macOS output: Test speakers' in w.routing.text()
        assert 'Required macOS output: BlackHole 2ch' in w.routing.text()
        assert 'ISLA Physical Playback: Test speakers' in w.routing.text()
        assert 'Check My Setup' in w.next_action.text()
        routing.snapshot = __import__('test_live').fake_routing().snapshot
        click(app, w, w.recheck)
        assert w.start_live.isEnabled()
        click(app, w, w.start_live)
        assert w.state.live_active and len(live.streams) == 1
        assert not w.start_live.isEnabled() and not w.capture.isEnabled()
        choose_live_mode(app, w, 'legato')
        assert c.live.mode == 'legato'
        click(app, w, w.stop_live)
        assert not w.state.live_active and live.streams[0].closed
    finally:
        close_window(app, w, c)



def test_running_live_mode_switches_reach_dsp_worker_and_health_stays_scrollable(app):
    """UI switches Bypass/Velvet/Legato/Melt without stopping or creating streams."""
    import numpy as np

    w, c, live, _, _, routing = window_session(app)
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        # Qt state is refreshed by its event timer; selection alone does not
        # synchronously enable the button until the next UI update.
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        click(app, w, w.start_live)
        assert len(live.streams) == 1
        stream = live.streams[0]

        # Actual StreamingDSP is fed by the fake transport, not replaced with
        # a mock. No native Mac audio or perceptual effect is claimed here.
        for _ in range(8):
            stream.pump(np.zeros((512, 2), np.float32))
        for mode in ('velvet', 'legato', 'melt', 'bypass'):
            choose_live_mode(app, w, mode)
            assert c.live.running and c.live.mode == mode
            assert w.live_mode_choice.currentData() == mode
            assert w.live_mode_choice.currentData() == mode
            stream.pump(np.full((512, 2), .12, np.float32))
            wait_ui(app, lambda: w.state.live_applied_mode == mode, timeout=5)
            assert c.live.processor.mode == mode
            assert 'DSP worker' in w.live_mode_status.text()
            assert len(live.streams) == 1

        # The visible diagnostics control has a real scrollbar. A changing
        # status snapshot must not forcibly return the user's viewport to top.
        bar = w.live_health.verticalScrollBar()
        assert bar.maximum() > 0
        bar.setValue(bar.maximum())
        previous = w.live_health.toPlainText()
        c.live.underflows += 3
        wait_ui(app, lambda: w.live_health.toPlainText() != previous)
        assert bar.value() == bar.maximum()
        bar.setValue(0)
        previous = w.live_health.toPlainText()
        c.live.underflows += 2
        wait_ui(app, lambda: w.live_health.toPlainText() != previous)
        assert bar.value() == 0
        assert 'Recovery attempts/completed/failed' in w.live_health.toPlainText()
        assert len(live.streams) == 1
        click(app, w, w.stop_live)
        assert live.streams[0].closed
    finally:
        close_window(app, w, c)


def test_start_live_original_explicit_reset_and_listening_volume(app):
    """Start resets Bypass; reselect is idempotent and Reset explicitly restores it."""
    w, c, backend, _, _, _ = window_session(app)
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        choose_live_mode(app, w, 'melt')
        assert c.live.mode == 'melt'
        click(app, w, w.start_live)
        assert c.live.mode == 'bypass'
        assert w.live_mode_choice.currentData() == 'bypass'
        assert len(backend.streams) == 1

        for name in ('velvet', 'legato', 'melt'):
            choose_live_mode(app, w, name)
            assert c.live.mode == name and w.live_mode_choice.currentData() == name
            assert w.live_mode_choice.count() == 4
            choose_live_mode(app, w, name)
            assert c.live.mode == name and w.live_mode_choice.currentData() == name
            click(app, w, w.reset_live_mode)
            assert c.live.mode == 'bypass' and w.live_mode_choice.currentData() == 'bypass'
            assert w.live_mode_choice.count() == 4
        choose_live_mode(app, w, 'velvet')
        choose_live_mode(app, w, 'bypass')
        assert c.live.mode == 'bypass'

        w.monitor_volume.setValue(35)
        wait_ui(app, lambda: w.state.monitor_volume == 35)
        assert w.state.monitor_volume == 35
        assert c.live.processor.volume.percent == 35
        assert '35%' in w.monitor_volume_status.text()
        click(app, w, w.mute_volume)
        wait_ui(app, lambda: w.state.monitor_volume == 0)
        assert w.state.monitor_volume == 0
        assert w.mute_volume.text() == 'Unmute'
        click(app, w, w.mute_volume)
        wait_ui(app, lambda: w.state.monitor_volume == 35)
        assert w.state.monitor_volume == 35
        assert len(backend.streams) == 1
        click(app, w, w.stop_live)
        assert backend.streams[0].closed
    finally:
        close_window(app, w, c)


def test_monitor_stop_is_not_blocked_by_gui_device_rescan(app, monkeypatch):
    """No scan during LIVE/Stop; deferred refresh follows returned audio cleanup."""
    w, c, live, _, _, routing = window_session(app)
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        click(app, w, w.start_live)
        assert w.state.live_active and len(live.streams) == 1
        assert not w.refresh.isEnabled() and not w.recheck.isEnabled()

        rescans = []
        stop_returned = threading.Event()
        service = w.worker.service
        original_scan = service.refresh_devices
        original_stop = service.stop_live
        def track_stop():
            result = original_stop()
            stop_returned.set()
            return result
        def track_scan(*args,**kwargs):
            # A post-Stop refresh may finish before this test thread consumes
            # the Stop completion event. Prove causal ordering rather than
            # assuming the GUI thread always wins that scheduling race.
            assert stop_returned.is_set(), 'Rescan started inside/before Stop'
            assert not c.live.running and live.streams[0].closed
            rescans.append('after Stop returned and stream closed')
            return original_scan(*args,**kwargs)
        monkeypatch.setattr(service, 'stop_live', track_stop)
        monkeypatch.setattr(service, 'refresh_devices', track_scan)
        # Force the background two-second threshold without sleeping two
        # seconds: worker must skip it while LIVE is running.
        w.worker._last_device_refresh = 0.
        wait_ui(app, lambda: w.worker._last_device_refresh != 0.)
        assert not rescans
        click(app, w, w.stop_live)
        assert not c.live.running and live.streams[0].closed
        assert stop_returned.is_set()
        wait_ui(app, lambda: bool(rescans) and w.state.routing_ready)
        assert w.refresh.isEnabled() and w.recheck.isEnabled()
    finally:
        close_window(app, w, c)


def test_monitor_safety_stop_displays_exact_reason(app):
    """A worker fault must explain spontaneous stop, not just say 'Fatal'."""
    w, c, live, _, _, _ = window_session(app)
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        click(app, w, w.start_live)
        reason = 'Audio device disconnected or callbacks stopped. Reconnect and monitor start.'
        c.live._fault(reason, device=True)
        wait_ui(app, lambda: not w.state.live_active and reason in w.live_error.text())
        assert w.state.live_state == UIState.FATAL_ERROR
        assert w.state.live_failure_reason == reason
        assert 'LIVE stopped safely' in w.live_error.text()
        assert reason in w.live_health.toPlainText()
        assert live.streams[0].closed
    finally:
        close_window(app, w, c)


def test_startup_capture_rejection_reaches_control_center_with_retained_counters(app):
    """Real monitor callbacks -> control snapshot -> widgets, no native device."""
    from types import SimpleNamespace
    import numpy as np
    from isla.live import BLOCK, WARMUP_BLOCKS

    w, c, live, *_ = window_session(app)
    try:
        prepare_live(app, w)
        stream = live.streams[0]
        gap = SimpleNamespace(input_overflow=True)
        block = np.zeros((BLOCK, 2), np.float32)
        for callback in range(1, WARMUP_BLOCKS + 2):
            assert not stream.pump(block, gap if callback >= WARMUP_BLOCKS - 1 else None).any()
        wait_ui(app, lambda: not w.state.live_active and 'continuing beyond startup' in w.live_error.text())
        assert w.state.live_state == UIState.FATAL_ERROR
        assert c.live.error == w.state.live_failure_reason
        assert 'budget exhausted' not in w.live_error.text()
        assert 'LIVE stopped safely' in w.live_error.text()
        assert 'Monitor: Failed' in w.live_health.toPlainText()
        assert 'Recovery attempts/completed/failed: 0 / 0 / 1' in w.live_health.toPlainText()
        assert 'Capture discontinuities (including startup): 3' in w.live_health.toPlainText()
        assert stream.closed and len(live.streams) == 1
        c.live.stop()
        assert 'continuing beyond startup' in c.live.status()
    finally:
        close_window(app, w, c)

def test_preparation_failure_recovers_with_error_visible_and_close_works(app):
    w, c, *_ = window_session(app)
    try:
        w.submit('load', 'bad.wav')
        wait_ui(app, lambda: not w.busy)
        def failed():
            raise ValueError('preparation worker failed')
        c.job.poll = failed
        wait_ui(app, lambda: 'worker failed' in w.global_error.text())
        assert not w.play.isEnabled() and w.open_file.isEnabled()
        w.submit('load', 'good.wav')
        wait_ui(app, lambda: not w.busy and c.job is not None)
        assert w.state.file_state == UIState.PREPARING
    finally:
        close_window(app, w, c)


def test_slow_worker_keeps_event_loop_responsive_and_defers_cli_handoff(app):
    w, c, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    def slow_prepare(path):
        entered.set()
        assert release.wait(timeout=5)
        return PendingPreparation(path)
    c.preparation_factory = slow_prepare
    try:
        assert w.submit('load', 'slow.wav')
        assert not w.submit('start')
        wait_ui(app, entered.is_set)
        pulses = []
        timer = QTimer()
        timer.timeout.connect(lambda: pulses.append(1))
        timer.start(5)
        w.started -= 11
        wait_ui(app, lambda: len(pulses) > 4)
        # The diagnostic is emitted by the window's 50 ms status timer,
        # not the independent 5 ms event-loop probe above. Wait for that
        # observable UI state rather than racing the next status poll.
        wait_ui(app, lambda: 'longer than expected' in w.global_error.text())
        w.close()
        assert w.isVisible() and c._window_owner is w.worker.service
        assert not w.closed_cleanly
        release.set()
        wait_ui(app, lambda: w.closed_cleanly)
        timer.stop()
        assert not c.closed and c._window_owner is None and c.job is None
    finally:
        release.set()
        if not w.closed_cleanly:
            close_window(app, w, c)
        else:
            c.close()


def test_close_failure_retains_window_then_retry_cleans_up(app):
    w, c, *_ = window_session(app)
    stop = c.live.stop
    c.live.stop = lambda: (_ for _ in ()).throw(RuntimeError('worker still stopping'))
    w.close()
    wait_ui(app, lambda: not w.busy and not w.closing)
    assert 'Cleanup is incomplete' in w.global_error.text()
    assert w.isVisible() and c._window_owner is not None
    c.live.stop = stop
    close_window(app, w, c)


def test_sound_settings_launchservices_and_manual_fallback(monkeypatch):
    import isla.qt_window as gui
    calls = []
    monkeypatch.setattr(gui.sys, 'platform', 'darwin')
    monkeypatch.setattr(gui.subprocess, 'run', lambda *a, **kw: calls.append((a, kw)))
    assert 'BlackHole 2ch' in open_sound_settings()
    assert calls[0][0][0][0] == '/usr/bin/open'
    assert calls[0][0][0][1].startswith('x-apple.systempreferences:')
    assert calls[0][1]['timeout'] == 5
    def failed(*a, **kw):
        raise OSError('LaunchServices unavailable')
    monkeypatch.setattr(gui.subprocess, 'run', failed)
    with pytest.raises(RuntimeError, match='Apple menu'):
        open_sound_settings()


@pytest.mark.parametrize('command', ['module', 'console', 'interactive'])
def test_actual_launch_forms_create_and_close_real_qt_window(tmp_path, command):
    # Test-only startup harness schedules a normal Close, so actual entrypoints
    # can run headlessly without adding a hidden production smoke-test flag.
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'sitecustomize.py').write_text('''
from PySide6.QtCore import QTimer
from isla.qt_window import ControlWindow
original = ControlWindow.showFullScreen
def show_fullscreen(self):
    original(self)
    assert self.isFullScreen(), "Control Center did not open full screen"
    print("ISLA_QT_WINDOW_FULLSCREEN", flush=True)
    QTimer.singleShot(700, self.close)
ControlWindow.showFullScreen = show_fullscreen
''')
    argv = ([sys.executable, '-m', 'isla', 'window'] if command == 'module' else
            [str(Path(sys.executable).parent / 'isla'), 'window'] if command == 'console' else
            [sys.executable, '-m', 'isla'])
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONPATH=os.pathsep.join([str(tmp_path), str(root)]))
    result = subprocess.run(argv, input='window\nwindow\nhelp\nexit\n' if command == 'interactive' else '',
                            text=True, capture_output=True, env=env, timeout=20, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ISLA_QT_WINDOW_FULLSCREEN' in result.stdout
    if command == 'interactive':
        assert result.stdout.count('ISLA_QT_WINDOW_FULLSCREEN') == 2
        assert 'Terminal ready' in result.stdout and 'Resources released' in result.stdout


def test_unexpected_command_worker_failure_releases_audio_without_hanging(app):
    w, c, *_ = window_session(app)
    w.submit('load', 'abrupt.wav')
    wait_ui(app, lambda: not w.busy)
    def abrupt():
        raise SystemExit('unexpected worker exit')
    c.job.poll = abrupt
    wait_ui(app, lambda: w.closed_cleanly)
    assert w.result_code == 1 and c._window_owner is None and c.job is None
    assert not c.closed
    c.close()


def test_unapplied_sample_rate_disables_start_until_applied(app):
    w, c, *_ = window_session(app)
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        assert w.start_live.isEnabled()
        w.rate.setCurrentIndex(0)
        wait_ui(app, lambda: not w.start_live.isEnabled())
        assert 'Use These Devices' in w.next_action.text()
        click(app, w, w.apply_devices)
        assert w.state.rate == 44100 and w.start_live.isEnabled()
    finally:
        close_window(app, w, c)


def test_real_preparation_process_from_window_worker(app, tmp_path):
    import numpy as np
    import soundfile as sf
    from isla.preparation import Preparation

    w, c, *_ = window_session(app)
    path = tmp_path / 'real piano.wav'
    audio = np.zeros((1024, 2), dtype=np.float32)
    sf.write(path, audio, 44100, subtype='FLOAT')
    c.preparation_factory = Preparation
    try:
        w.submit('load', str(path))
        wait_ui(app, lambda: w.state.file_state == UIState.READY, timeout=15)
        np.testing.assert_array_equal(c.player.buffers['original'], audio)
        assert c.player.sr == 44100 and w.play.isEnabled()
        directory = Path(c.job.directory.name)
        assert directory.is_dir()
    finally:
        close_window(app, w, c)
    assert not directory.exists()


@pytest.mark.parametrize('running', [False, True])
def test_live_mode_pending_selection_survives_old_snapshots(app, monkeypatch, running):
    """Real key activation must retain intent before the command worker returns."""
    w, c, backend, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        click(app, w, w.apply_devices)
        if running:
            click(app, w, w.start_live)
        original = w.worker.service.live_mode
        def delayed(mode):
            entered.set()
            assert release.wait(5)
            original(mode)
        monkeypatch.setattr(w.worker.service, 'live_mode', delayed)
        combo = w.live_mode_choice
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_Down)
        wait_ui(app, entered.is_set)
        for _ in range(5):
            w.apply_state()  # Last confirmed snapshot is still Bypass.
            app.processEvents()
            assert combo.currentData() == 'velvet'
        release.set()
        wait_ui(app, lambda: not w.busy)
        assert combo.currentData() == c.live.mode == 'velvet'
        assert len(backend.streams) == int(running)
    finally:
        release.set()
        close_window(app, w, c)


def test_live_mode_popup_survives_periodic_refresh(app):
    w, c, *_ = window_session(app)
    try:
        w.submit('devices', w.state.captures[0], w.state.outputs[0], 48000)
        wait_ui(app, lambda: not w.busy)
        combo = w.live_mode_choice
        QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
        assert combo.view().isVisible()
        for _ in range(5):
            w.apply_state()
            app.processEvents()
            assert combo.view().isVisible(), 'Health refresh dismissed the mode picker'
        QTest.keyClick(combo, Qt.Key.Key_Escape)
    finally:
        close_window(app, w, c)


def prepare_live(app, w, *, start=True):
    w.submit('devices', w.state.captures[0], w.state.outputs[0], 48000)
    wait_ui(app, lambda: not w.busy)
    if start:
        click(app, w, w.start_live)


def test_rapid_native_modes_ordered_once_stale_snapshot_ignored_and_external_sync(app, monkeypatch):
    w, c, live, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    try:
        prepare_live(app, w)
        old_sequence, old_state = w._state_sequence, w.state
        original = w.worker.service.live_mode
        calls, rescans = [], []
        def delayed(mode):
            calls.append(mode)
            if len(calls) == 1:
                entered.set()
                assert release.wait(5)
            return original(mode)
        monkeypatch.setattr(w.worker.service, 'live_mode', delayed)
        monkeypatch.setattr(w.worker.service, 'refresh_devices', lambda: rescans.append(1))
        activate_live_mode(app, w, 'velvet')
        wait_ui(app, entered.is_set)
        # Native keyboard activations while the previous command is delayed.
        QTest.keyClick(w.live_mode_choice, Qt.Key.Key_Down)  # Legato
        QTest.keyClick(w.live_mode_choice, Qt.Key.Key_Down)  # Melt
        assert w.live_mode_choice.currentData() == 'melt'
        assert 'Requested: Melt' in w.live_mode_status.text()
        # Delayed health events cannot restore an older confirmed choice.
        for _ in range(6):
            w.worker.events.put(('state', (old_sequence, old_state)))
            w.drain_events()
            assert w.live_mode_choice.currentData() == 'melt'
        release.set()
        wait_ui(app, lambda: not w.busy and not w._mode_requests)
        assert calls == ['velvet', 'legato', 'melt']
        assert w.state.live_mode == 'melt' and c.live.mode == 'melt'
        w.worker.events.put(('state', (old_sequence, old_state)))
        w.drain_events()
        assert w.live_mode_choice.currentData() == 'melt'
        w.output.setFocus()
        app.processEvents()
        assert w.live_mode_choice.currentData() == 'melt'
        # The supported owning worker can also change the backend directly.
        w.submit('live_mode', 'legato')
        wait_ui(app, lambda: not w.busy)
        assert w.live_mode_choice.currentData() == 'legato'
        # Same-item mouse activation is idempotent, explicit Reset is testable.
        choose_live_mode(app, w, 'legato')
        assert calls == ['velvet', 'legato', 'melt', 'legato']
        click(app, w, w.reset_live_mode)
        assert calls[-1] == 'bypass'
        assert not rescans and len(live.streams) == 1 and not live.streams[0].closed
    finally:
        release.set()
        close_window(app, w, c)


def test_rejected_live_mode_rolls_back_and_error_survives_healthy_poll(app, monkeypatch):
    from dataclasses import replace
    w, c, live, *_ = window_session(app)
    try:
        prepare_live(app, w)
        choose_live_mode(app, w, 'velvet')
        original = w.worker.service.live_mode
        def rejected(mode):
            raise RuntimeError('test mode selection rejected')
        monkeypatch.setattr(w.worker.service, 'live_mode', rejected)
        choose_live_mode(app, w, 'melt')
        assert w.live_mode_choice.currentData() == c.live.mode == 'velvet'
        assert 'test mode selection rejected' in w.live_error.text()
        # Even a healthy later snapshot must not erase the operator's error.
        sequence = w._state_sequence + 1
        w.worker.events.put(('state', (sequence, replace(w.state, error=''))))
        w.drain_events()
        assert 'test mode selection rejected' in w.live_error.text()
        assert w.live_mode_choice.isEnabled() and w.stop_live.isEnabled()
        monkeypatch.setattr(w.worker.service, 'live_mode', original)
        choose_live_mode(app, w, 'legato')
        assert c.live.mode == 'legato' and not w.live_error.text()
        assert len(live.streams) == 1 and not live.streams[0].closed
    finally:
        close_window(app, w, c)


def test_mode_ack_and_last_applied_dsp_state_remain_distinct_during_block(app, monkeypatch):
    import numpy as np
    w, c, live, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    try:
        prepare_live(app, w)
        processor = c.live.processor
        original = processor.process_block
        def blocked(block):
            entered.set()
            assert release.wait(5)
            return original(block)
        monkeypatch.setattr(processor, 'process_block', blocked)
        stream = live.streams[0]
        # Feed startup hops one at a time without filling the bounded ring.
        from isla.live import WARMUP_BLOCKS
        for _ in range(WARMUP_BLOCKS + 1):
            stream.pump(np.zeros((512, 2), np.float32))
            if entered.wait(.02):
                break
        wait_ui(app, entered.is_set)
        choose_live_mode(app, w, 'velvet')
        assert w.state.live_mode == 'velvet' and w.state.live_applied_mode == 'bypass'
        assert 'waiting for the next processed audio block' in w.live_mode_status.text()
        release.set()
        wait_ui(app, lambda: c.live.output.count > 0)
        stream.pump(np.full((512, 2), .01, np.float32))
        wait_ui(app, lambda: w.state.live_applied_mode == 'velvet')
        assert 'DSP worker' in w.live_mode_status.text()
        assert len(live.streams) == 1 and c.live.running
    finally:
        release.set()
        close_window(app, w, c)


@pytest.mark.parametrize('action', ['stop', 'close'])
def test_stop_or_close_during_pending_mode_drops_only_unsent_modes(app, monkeypatch, action):
    w, c, live, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    try:
        prepare_live(app, w)
        original = w.worker.service.live_mode
        calls = []
        def delayed(mode):
            calls.append(mode)
            entered.set()
            assert release.wait(5)
            return original(mode)
        monkeypatch.setattr(w.worker.service, 'live_mode', delayed)
        activate_live_mode(app, w, 'velvet')
        wait_ui(app, entered.is_set)
        QTest.keyClick(w.live_mode_choice, Qt.Key.Key_Down)  # Queued Legato.
        if action == 'stop':
            assert w.stop_live.isEnabled()
            QTest.mouseClick(w.stop_live, Qt.MouseButton.LeftButton)
        else:
            w.close()
        assert w.isVisible() and c._window_owner is not None
        release.set()
        wait_ui(app, lambda: w.closed_cleanly if action == 'close' else not w.busy and not c.live.running)
        assert calls == ['velvet'] and len(live.streams) == 1 and live.streams[0].closed
    finally:
        release.set()
        if not w.closed_cleanly:
            close_window(app, w, c)
        else:
            w.worker.thread.join(2)
            assert c._window_owner is None
            c.close()


def test_popup_mouse_item_selection_survives_snapshot_and_focus_change(app):
    """Hit-test an actual native combo item with the mouse after a health tick."""
    w, c, live, *_ = window_session(app)
    try:
        prepare_live(app, w)
        combo = w.live_mode_choice
        QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
        app.processEvents()
        w.apply_state()
        assert combo.view().isVisible()
        item = combo.model().index(combo.findData('melt'), 0)
        combo.view().scrollTo(item)
        QTest.mouseMove(combo.view().viewport(), QPoint(2, 2))
        QTest.mouseMove(combo.view().viewport(), combo.view().visualRect(item).center())
        QTest.mouseClick(combo.view().viewport(), Qt.MouseButton.LeftButton,
                         pos=combo.view().visualRect(item).center())
        wait_ui(app, lambda: not w.busy and w.state.live_mode == 'melt')
        assert combo.currentData() == 'melt'
        w.reset_live_mode.setFocus()
        app.processEvents()
        assert combo.currentData() == 'melt'
        QTest.keyClick(w.reset_live_mode, Qt.Key.Key_Space)
        wait_ui(app, lambda: not w.busy and w.state.live_mode == 'bypass')
        assert combo.currentData() == 'bypass' and len(live.streams) == 1
    finally:
        close_window(app, w, c)
