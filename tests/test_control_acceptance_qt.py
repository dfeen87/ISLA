"""Dashboard interaction acceptance with fake devices, never acoustic evidence."""
from pathlib import Path
from types import SimpleNamespace
import threading

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog

from isla.control import UIState
from isla.preparation import Preparation
from test_control import prepared_buffers
from isla.qt_window import CommandWorker, ControlWindow
from test_qt_window import app, click, close_window, wait_ui, window_session
from test_remastered_preparation import DeferredRender


def held_click(app, w, button):
    """Exercise a press/release across repeated real snapshot application."""
    assert button.isEnabled(), button.text()
    QTest.mousePress(button, Qt.MouseButton.LeftButton)
    try:
        for _ in range(3):
            w.drain_events()
            app.processEvents()
            assert button.isEnabled() and button.isDown(), button.text()
    finally:
        QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
    wait_ui(app, lambda: not w.busy)


def load_ready(app, w, c):
    w.submit('load', 'prepared.wav')
    wait_ui(app, lambda: not w.busy)
    c.job.result = prepared_buffers(), 48000
    wait_ui(app, lambda: w.state.can_play)


def test_picker_cancel_invalid_format_missing_file_and_real_reload(app, monkeypatch, tmp_path):
    w, c, _, files, *_ = window_session(app)
    c.preparation_factory = Preparation
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('', ''))
        held_click(app, w, w.open_file)
        assert c.job is None and w.state.file_state == UIState.NO_FILE
        invalid = tmp_path / 'unsupported.wav'
        invalid.write_text('this is not an audio recording')
        for path, error in ((tmp_path / 'missing.wav', 'Audio file not found'),
                            (invalid, 'Unsupported or invalid audio file')):
            monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(path), ''))
            held_click(app, w, w.open_file)
            assert error in w.global_error.text() and error in w.file_error.text()
            assert w.open_file.isEnabled() and not w.play.isEnabled()
            assert c.job is None and not files.streams
        source = tmp_path / 'valid.wav'
        x = np.full((4096, 2), .1, np.float32)
        sf.write(source, x, 48000, subtype='FLOAT')
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(source), ''))
        held_click(app, w, w.open_file)
        wait_ui(app, lambda: w.state.file_state == UIState.READY, timeout=15)
        assert str(source) == w.filename.text() and not w.global_error.text()
        np.testing.assert_array_equal(c.player.buffers['original'], x)
        held_click(app, w, w.play)
        stream = files.streams[0]
        stream.pump()
        wait_ui(app, lambda: w.state.position > 0)
        held_click(app, w, w.pause)
        assert w.state.file_state == UIState.PAUSED
        paused_position = c.player.position
        assert stream.closed  # Existing Pause releases the physical stream.
        held_click(app, w, w.play)
        assert c.player.position == paused_position
        held_click(app, w, w.stop_file)
        assert w.state.position == 0 and len(files.streams) == 2
        assert all(s.closed for s in files.streams)
    finally:
        close_window(app, w, c)


def test_replacing_pending_preparation_closes_old_job_and_ignores_old_result(app, monkeypatch):
    w, c, *_ = window_session(app)
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('first.wav', ''))
        held_click(app, w, w.open_file)
        first = c.job
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('second.wav', ''))
        held_click(app, w, w.open_file)
        assert first.closed and c.job is not first
        first.result = prepared_buffers(), 44100
        assert w.filename.text() == 'second.wav' and not w.play.isEnabled()
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        assert c.player.sr == 48000 and c.path == Path('second.wav')
    finally:
        close_window(app, w, c)


def test_device_and_rate_drafts_poll_apply_and_stale_output_recovery(app):
    w, c, _, files, devices, routing = window_session(app)
    try:
        native, default = routing.snapshot()
        native.append(dict(id=22, name='Test Bluetooth', transport='blue',
                           alive=True, input=False, output=True))
        devices.append(dict(name='Test Bluetooth', max_input_channels=0, max_output_channels=2))
        routing.snapshot = lambda: (native, default)
        held_click(app, w, w.refresh)
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(2)
        w.rate.setFocus()
        QTest.keyClick(w.rate, Qt.Key.Key_Home)
        w.research_toggle.setFocus()
        for _ in range(3):
            w.drain_events()
            assert w.output.currentData().native_id == 22 and w.rate.currentData() == 44100
        held_click(app, w, w.apply_devices)
        assert c.output == 'Test Bluetooth' and w.state.rate == 44100
        assert w.start_live.isEnabled()
        held_click(app, w, w.refresh)
        assert w.output.currentData() == w.state.selected_output
        assert w.rate.currentData() == w.state.rate == 44100
        # An output disappearing after selection must fail at authoritative recheck.
        native[-1]['alive'] = False
        held_click(app, w, w.apply_output)
        assert 'stale' in w.file_error.text().lower()
        assert not w.start_live.isEnabled() and not files.streams
        w.file_output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_output.isEnabled())
        held_click(app, w, w.apply_output)
        assert c.output == w.state.selected_output.name == 'Test speakers'
        assert not w.global_error.text()
    finally:
        close_window(app, w, c)


def test_rejected_live_engine_and_depth_restore_backend_confirmed_controls(app, monkeypatch):
    w, c, *_ = window_session(app)
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        held_click(app, w, w.apply_devices)
        method = w.worker.service.set_live_processing
        def reject(*args):
            raise RuntimeError('engine change rejected by backend')
        monkeypatch.setattr(w.worker.service, 'set_live_processing', reject)
        w.live_engine.setFocus()
        QTest.keyClick(w.live_engine, Qt.Key.Key_End)  # Native activation auto-applies.
        wait_ui(app, lambda: not w.busy)
        assert 'engine change rejected' in w.live_error.text()
        assert w.live_engine.currentData() == w.state.live_engine == 'production'
        w.live_intensity.setFocus()
        QTest.keyClick(w.live_intensity, Qt.Key.Key_Home)
        held_click(app, w, w.apply_live_intensity)
        assert w.live_intensity.value() * 5 == w.state.live_intensity == 100
        assert w.live_engine.isEnabled() and w.start_live.isEnabled()
        monkeypatch.setattr(w.worker.service, 'set_live_processing', method)
        w.live_engine.setFocus()
        QTest.keyClick(w.live_engine, Qt.Key.Key_End)
        wait_ui(app, lambda: not w.busy and w.state.live_engine == 'remastered')
        assert w.live_engine.currentData() == 'remastered' and not w.live_error.text()
    finally:
        close_window(app, w, c)


def test_live_start_rejection_and_duplicate_submissions_recover_without_orphans(app, monkeypatch):
    w, c, live, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    try:
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        held_click(app, w, w.apply_devices)
        live.failure = 'physical output unavailable'
        held_click(app, w, w.start_live)
        assert 'physical output unavailable' in w.live_error.text()
        assert not w.state.live_active and not live.streams
        live.failure = None
        original = w.worker.service.start_live
        calls = []
        def delayed_start():
            calls.append('start')
            entered.set()
            assert release.wait(5)
            return original()
        monkeypatch.setattr(w.worker.service, 'start_live', delayed_start)
        QTest.mouseClick(w.start_live, Qt.MouseButton.LeftButton)
        wait_ui(app, entered.is_set)
        assert not w.start_live.isEnabled() and not w.submit('start')
        QTest.mouseClick(w.start_live, Qt.MouseButton.LeftButton)
        release.set()
        wait_ui(app, lambda: not w.busy and w.state.live_active)
        assert calls == ['start'] and len(live.streams) == 1
        held_click(app, w, w.stop_live)
        assert live.streams[0].closed and not c.live.running
    finally:
        release.set()
        close_window(app, w, c)


def test_remastered_all_modes_exact_intensity_steps_cancel_and_return(app, tmp_path):
    w, c, live, files, *_ = window_session(app)
    try:
        load_ready(app, w, c)
        np.save(tmp_path / 'original.npy', c.player.buffers['original'])
        c.job.directory = SimpleNamespace(name=str(tmp_path))
        w.worker.service.preview.factory = DeferredRender
        click(app, w, w.file_modes['legato'])
        click(app, w, w.research_toggle)
        held_click(app, w, w.enter_research)
        assert w.state.research_previous_mode == 'legato' and c.player.mode == 'original'
        assert not any(b.isEnabled() for b in w.file_modes.values())
        w.research_intensity.setFocus()
        QTest.keyClick(w.research_intensity, Qt.Key.Key_Home)
        for tick in range(21):
            if tick:
                QTest.keyClick(w.research_intensity, Qt.Key.Key_Right)
            assert w.research_intensity.value() * 5 == tick * 5
            assert w.research_intensity_value.text() == f'{tick * 5}% permitted depth'
            for mode in ('velvet', 'legato', 'melt'):
                w.research_mode.setCurrentIndex(w.research_mode.findData(mode))
                held_click(app, w, w.apply_research)
                request = w.worker.service.preview.job.request
                assert (request.mode, request.intensity) == (mode, tick * 5)
                job = w.worker.service.preview.job
                assert w.state.research_pending and w.cancel_research.isEnabled()
                # Collapse cannot hide the real cancellation action.
                click(app, w, w.research_toggle)
                assert w.cancel_research.isVisible()
                held_click(app, w, w.cancel_research)
                assert job.closed and not w.state.research_pending
                assert not w.state.research_workspace and c.player.mode == 'legato'
                click(app, w, w.research_toggle)
                held_click(app, w, w.enter_research)
        held_click(app, w, w.return_research)
        assert c.player.mode == 'legato' and not live.streams and not files.streams
    finally:
        close_window(app, w, c)


def test_save_picker_cancel_collision_and_contextual_cancel_reach_writer(app, monkeypatch, tmp_path):
    w, c, _, files, *_ = window_session(app)
    entered, release = threading.Event(), threading.Event()
    try:
        load_ready(app, w, c)
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: ('', ''))
        held_click(app, w, w.save_mix_button)
        assert not w.state.save_pending and not list(tmp_path.iterdir())
        existing = tmp_path / 'original.wav'
        existing.write_bytes(b'protected recording')
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(existing), ''))
        held_click(app, w, w.save_mix_button)
        assert 'already exists' in w.file_error.text()
        assert existing.read_bytes() == b'protected recording'
        # Pause the real writer at its first chunk, then cancel through the UI.
        original_write = sf.SoundFile.write
        export = w.worker.service.mix_export
        def blocked_write(output, data):
            entered.set()
            assert release.wait(5)
            return original_write(output, data)
        monkeypatch.setattr(sf.SoundFile, 'write', blocked_write)
        target = tmp_path / 'cancel.wav'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(target), ''))
        held_click(app, w, w.save_mix_button)
        wait_ui(app, entered.is_set)
        assert w.cancel_research.text() == 'Cancel Save' and w.export_progress.isVisible()
        QTest.mouseClick(w.cancel_research, Qt.MouseButton.LeftButton)
        wait_ui(app, export._cancel.is_set)
        release.set()
        wait_ui(app, lambda: not w.busy and not w.state.save_pending)
        assert 'canceled' in w.export_status.text()
        assert not target.exists() and not list(tmp_path.glob('.isla-mix-*'))
        assert not files.streams and w.save_mix_button.isEnabled()
    finally:
        release.set()
        close_window(app, w, c)


def test_three_workspace_transitions_and_reopen_release_single_audio_owner(app, tmp_path):
    w, c, live, files, *_ = window_session(app)
    try:
        load_ready(app, w, c)
        np.save(tmp_path / 'original.npy', c.player.buffers['original'])
        c.job.directory = SimpleNamespace(name=str(tmp_path))
        click(app, w, w.file_modes['melt'])
        held_click(app, w, w.play)
        alive_stream = c.player.stream
        assert not w.start_live.isEnabled() and not w.apply_devices.isEnabled()
        click(app, w, w.research_toggle)
        held_click(app, w, w.enter_research)
        assert c.player.stream is alive_stream and len(files.streams) == 1
        held_click(app, w, w.return_research)
        assert c.player.mode == 'melt' and c.player.stream is alive_stream
        held_click(app, w, w.stop_file)
        w.capture.setCurrentIndex(1)
        w.output.setCurrentIndex(1)
        wait_ui(app, lambda: w.apply_devices.isEnabled())
        held_click(app, w, w.apply_devices)
        held_click(app, w, w.start_live)
        assert alive_stream.closed and len(live.streams) == 1
        assert not w.play.isEnabled() and not w.enter_research.isEnabled()
        held_click(app, w, w.stop_live)
        held_click(app, w, w.play)
        assert c.source == 'file' and len(files.streams) == 2 and live.streams[0].closed
        w.close()
        wait_ui(app, lambda: w.closed_cleanly)
        w.worker.thread.join(timeout=2)
        assert not w.worker.thread.is_alive() and c._window_owner is None
        assert all(stream.closed for stream in (*files.streams, *live.streams))
        worker = CommandWorker(c)
        w = ControlWindow(worker)
        w.show()
        worker.start()
        wait_ui(app, lambda: w.state is not None and not w.busy)
        assert w.state.can_play and not w.state.stream_active
        held_click(app, w, w.play)
        assert len(files.streams) == 3 and not c.live.running
    finally:
        close_window(app, w, c)


@pytest.mark.parametrize('failure_stage', ['write', 'publish'])
def test_save_failure_cleans_staging_and_retry_exports_exact_pcm(app, monkeypatch, tmp_path, failure_stage):
    w, c, _, files, *_ = window_session(app)
    try:
        load_ready(app, w, c)
        target = tmp_path / 'retry.wav'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(target), ''))
        with monkeypatch.context() as failure:
            if failure_stage == 'write':
                original_write = sf.SoundFile.write
                def partial_write(output, data):
                    original_write(output, data)
                    raise OSError('test disk write failed')
                failure.setattr(sf.SoundFile, 'write', partial_write)
            else:
                def rejected_publish(*args):
                    raise PermissionError('test publication failed')
                failure.setattr('isla.mix_export.os.link', rejected_publish)
            held_click(app, w, w.save_mix_button)
            wait_ui(app, lambda: not w.state.save_pending and 'failed' in w.export_status.text())
        assert not target.exists() and not list(tmp_path.glob('.isla-mix-*'))
        assert not w.state.saved_path and w.save_mix_button.isEnabled()
        held_click(app, w, w.save_mix_button)
        wait_ui(app, lambda: w.state.saved_path == str(target))
        saved, rate = sf.read(target, dtype='float32', always_2d=True)
        np.testing.assert_array_equal(saved, c.player.buffers['original'])
        assert rate == 48000 and not files.streams
    finally:
        close_window(app, w, c)
