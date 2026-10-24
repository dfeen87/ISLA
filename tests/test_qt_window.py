"""Real Qt widget tests, offscreen; not native macOS/audio acceptance."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from isla.control import UIState
from isla.qt_window import CommandWorker, ControlWindow, open_sound_settings
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


def test_widgets_disable_unprepared_controls_and_real_file_lifecycle(app, monkeypatch):
    w, c, live, files, *_ = window_session(app)
    try:
        assert w.windowTitle() == 'ISLA — Audio Control Center'
        assert w.file_status.text() == 'Open an audio file to begin'
        assert not w.play.isEnabled() and not w.pause.isEnabled()
        assert not any(b.isEnabled() for b in w.file_modes.values())
        assert not w.start_live.isEnabled()
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('piano with spaces.wav', ''))
        click(app, w, w.open_file)
        assert w.state.file_state == UIState.PREPARING
        assert not w.play.isEnabled()
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        click(app, w, w.play)
        assert w.state.file_state == UIState.PLAYING and w.pause.isEnabled()
        assert not w.open_file.isEnabled() and not w.output.isEnabled()
        click(app, w, w.file_modes['melt'])
        assert c.player.mode == 'melt' and len(files.streams) == 1
        click(app, w, w.file_modes['bypass'])
        assert c.player._selected is c.player.buffers['original']
        click(app, w, w.pause)
        assert w.state.file_state == UIState.PAUSED
        click(app, w, w.stop_file)
        assert w.state.position == 0
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
        assert 'Recheck Audio Routing' in w.next_action.text()
        routing.snapshot = __import__('test_live').fake_routing().snapshot
        click(app, w, w.recheck)
        assert w.start_live.isEnabled()
        click(app, w, w.start_live)
        assert w.state.live_active and len(live.streams) == 1
        assert not w.start_live.isEnabled() and not w.capture.isEnabled()
        click(app, w, w.live_modes['legato'])
        assert c.live.mode == 'legato'
        click(app, w, w.stop_live)
        assert not w.state.live_active and live.streams[0].closed
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
        assert 'longer than expected' in w.global_error.text()
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
original = ControlWindow.show
def show(self):
    original(self)
    print("ISLA_QT_WINDOW_SHOWN", flush=True)
    QTimer.singleShot(700, self.close)
ControlWindow.show = show
''')
    argv = ([sys.executable, '-m', 'isla', 'window'] if command == 'module' else
            [str(Path(sys.executable).parent / 'isla'), 'window'] if command == 'console' else
            [sys.executable, '-m', 'isla'])
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONPATH=os.pathsep.join([str(tmp_path), str(root)]))
    result = subprocess.run(argv, input='window\nwindow\nhelp\nexit\n' if command == 'interactive' else '',
                            text=True, capture_output=True, env=env, timeout=20, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ISLA_QT_WINDOW_SHOWN' in result.stdout
    if command == 'interactive':
        assert result.stdout.count('ISLA_QT_WINDOW_SHOWN') == 2
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
        assert 'Apply LIVE Devices' in w.next_action.text()
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
