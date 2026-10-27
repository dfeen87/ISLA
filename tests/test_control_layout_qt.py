"""Visual layout and telemetry split contract; not native audio acceptance."""
import os
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QScrollArea

from isla.control import UIState
from isla.qt_window import audio_diagnostics, footer_visual_mode
from test_qt_window import app, window_session, close_window, wait_ui
from test_control import prepared_buffers


@pytest.mark.parametrize('size', [
    (1100, 950), (1040, 830), (800, 600), (640, 600), (1440, 900)
])
def test_three_columns_lower_telemetry_and_research_controls(app, size):
    w, controller, *_ = window_session(app)
    try:
        w.resize(*size)
        app.processEvents()
        scroll = w.findChild(QScrollArea)
        grid = scroll.widget().layout()
        alive, remastered, live, diagnostics = (
            w._alive_panel, w._remastered_panel_widget,
            w._live_panel_widget, w._telemetry_panel,
        )
        assert [panel.title() for panel in (alive, remastered, live)] == [
            'ALIVE — Local Audio File', 'ALIVE Remastered',
            'LIVE — Mac System Audio']
        compact = size[0] < 1080
        assert w._panel_compact is compact
        if compact:
            assert all(
                grid.itemAtPosition(i, 0).widget() is panel
                for i, panel in enumerate((alive, live, remastered, diagnostics))
            )
        else:
            assert grid.itemAtPosition(0, 0).widget() is alive
            assert grid.itemAtPosition(0, 1).widget() is remastered
            assert grid.itemAtPosition(0, 2).widget() is live
            assert grid.itemAtPosition(1, 0).widget() is diagnostics
            assert grid.itemAtPosition(1, 1).widget() is diagnostics
            assert grid.itemAtPosition(1, 2).widget() is live
        assert diagnostics.title() == 'Diagnostics — ALIVE / LIVE'
        if not compact:
            assert diagnostics.geometry().top() >= alive.geometry().bottom()
        else:
            assert live.geometry().top() >= alive.geometry().bottom()
        assert alive.isAncestorOf(w.play)
        assert remastered.isAncestorOf(w.research_panel)
        assert remastered.isAncestorOf(w.save_mix_button)
        assert remastered.isAncestorOf(w.monitor_volume)
        assert remastered.isAncestorOf(w.mute_volume)
        assert live.isAncestorOf(w.start_live) and live.isAncestorOf(w.stop_live)
        assert live.isAncestorOf(w.live_engine)
        assert diagnostics.isAncestorOf(w.health)
        assert diagnostics.isAncestorOf(w.live_health)
        assert diagnostics.isAncestorOf(w.processing_health)
        assert w.timer.interval() == 50

        # Remastered is now a permanent workspace, not an opt-in collapse.
        assert w.research_panel.title() == 'Experimental ALIVE Remastering'
        assert w.research_panel.isVisible()
        assert not hasattr(w, 'research_toggle')
        assert all(widget.isVisible() for widget in (
            w.enter_research, w.research_mode, w.research_intensity,
            w.apply_research, w.save_mix_button, w.cancel_research,
            w.return_research, w.health, w.live_health,
            w.monitor_volume, w.mute_volume))
        for control in (
            w.open_file, w.play, w.pause, w.stop_file,
            w.alive_volume, w.file_output, w.apply_output,
            *w.file_modes.values(), w.enter_research,
            w.research_mode, w.research_intensity, w.apply_research,
            w.save_mix_button, w.cancel_research, w.return_research,
            w.capture, w.output, w.rate, w.apply_devices, w.settings,
            w.recheck, w.start_live, w.stop_live, w.live_engine,
            w.live_intensity, w.apply_live_intensity,
            w.live_mode_choice, w.reset_live_mode, w.monitor_volume,
            w.mute_volume, w.health, w.live_health,
        ):
            assert control.parentWidget().rect().contains(control.geometry())
            if hasattr(control, 'text') and control.text():
                assert control.width() >= control.minimumSizeHint().width()
            # Respect scroll-area boundaries without hiding any controls.
            target = control.mapTo(scroll.widget(), control.rect().center())
            scroll.ensureVisible(target.x(), target.y(), 12, 12)
            app.processEvents()
            center = control.mapTo(scroll.viewport(), control.rect().center())
            assert scroll.viewport().rect().contains(center), (
                f'{control.objectName() or type(control).__name__}: '
                f'center={center}, viewport={scroll.viewport().rect()}')
        # ALL supported window sizes must have no horizontally clipped actions.
        assert scroll.horizontalScrollBar().maximum() == 0
    finally:
        close_window(app, w, controller)


@pytest.mark.parametrize('width', [640, 800, 1040, 1100, 1440])
def test_action_buttons_fully_visible_after_vertical_scrolling(app, width):
    w, controller, *_ = window_session(app)
    try:
        w.resize(width, 750)
        app.processEvents()
        scroll = w.findChild(QScrollArea)
        assert scroll.horizontalScrollBar().maximum() == 0
        controls = (
            w.open_file, w.play, w.pause, w.stop_file,
            *w.file_modes.values(), w.apply_output, w.enter_research,
            w.apply_research, w.save_mix_button, w.cancel_research,
            w.return_research,
            w.apply_devices, w.settings, w.recheck,
            w.start_live, w.stop_live, w.apply_live_intensity,
            w.reset_live_mode, w.mute_volume,
        )
        for control in controls:
            assert control.isVisible()
            scroll.ensureWidgetVisible(control, 12, 12)
            app.processEvents()
            bounds = scroll.viewport().rect()
            upper = control.mapTo(scroll.viewport(), control.rect().topLeft())
            lower = control.mapTo(scroll.viewport(), control.rect().bottomRight())
            assert bounds.contains(upper) and bounds.contains(lower), (
                f'button split/clipped: {control.text()} at {width}px: '
                f'{upper}..{lower} vs {bounds}'
            )
    finally:
        close_window(app, w, controller)


@pytest.mark.parametrize('width', [800, 1100])
def test_scrolled_alive_buttons_can_drive_prepared_playback(app, monkeypatch, width):
    w, controller, *_ = window_session(app)
    try:
        w.resize(width, 700)
        app.processEvents()
        scroll = w.findChild(QScrollArea)
        monkeypatch.setattr(
            QFileDialog, 'getOpenFileName',
            lambda *args: ('responsive playback.wav', '')
        )
        scroll.ensureWidgetVisible(w.open_file, 12, 12)
        QTest.mouseClick(w.open_file, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: w.state.file_state == UIState.PREPARING)
        controller.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.file_state == UIState.READY)
        assert w.play.isEnabled()
        scroll.ensureWidgetVisible(w.play, 12, 12)
        app.processEvents()
        QTest.mouseClick(w.play, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: w.state.file_state == UIState.PLAYING)
        assert w.pause.isEnabled()
        scroll.ensureWidgetVisible(w.pause, 12, 12)
        QTest.mouseClick(w.pause, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: w.state.file_state == UIState.PAUSED)
        scroll.ensureWidgetVisible(w.stop_file, 12, 12)
        QTest.mouseClick(w.stop_file, Qt.MouseButton.LeftButton)
        wait_ui(app, lambda: w.state.file_state == UIState.STOPPED)
    finally:
        close_window(app, w, controller)


def test_live_controls_reflect_backend_state_without_starting_or_restarting_audio(app):
    w, controller, *_ = window_session(app)
    original = w.state
    try:
        app.processEvents()
        assert w.live_state_indicator.accessibleName() == 'LIVE monitor state and safety outcome'
        assert w.start_live.objectName() == 'liveStartAction'
        assert w.stop_live.objectName() == 'liveStopAction'
        assert w.live_state_indicator.property('monitorState') == 'idle'
        assert w._live_panel_widget.layout().itemAt(
            w._live_panel_widget.layout().count() - 1).spacerItem() is not None
        assert w.live_mode_choice.count() == 4
        assert [w.live_mode_choice.itemData(i) for i in range(4)] == [
            'bypass', 'velvet', 'legato', 'melt']
        assert all(name in w.styleSheet() for name in (
            '#liveStartAction', '#liveStopAction', '#liveStateIndicator'))

        # Synthetic snapshots are UI-only. No fake command may reach native audio.
        w.state = replace(original, live_state=UIState.LIVE_RUNNING,
            live_active=True, stream_active=True, can_start=False, source='system',
            live_failure_reason='')
        w.apply_state()
        assert w.start_live.property('monitorState') == 'running'
        assert w.live_state_indicator.property('monitorState') == 'running'
        assert 'native stream running' in w.live_state_indicator.text()
        assert not w.start_live.isEnabled()

        reason = 'Input buffer overflow/contention; stopped rather than accumulating delayed audio.'
        w.state = replace(original, live_state=UIState.FATAL_ERROR,
            live_active=False, stream_active=False, can_start=False, source='system',
            live_failure_reason=reason)
        w.apply_state()
        assert w.start_live.property('monitorState') == 'failed'
        assert w.live_state_indicator.property('monitorState') == 'failed'
        assert reason in w.live_state_indicator.text()
        assert 'safety protection' in w.live_state_indicator.text().lower()
        assert not w.start_live.isEnabled()
        assert not controller.live.running
    finally:
        w.state = original
        close_window(app, w, controller)


def test_split_telemetry_retains_every_original_diagnostic_line(app):
    w, controller, *_ = window_session(app)
    try:
        app.processEvents()
        # No parsing, reformatting, deleted counters or redacted failure states.
        unified = audio_diagnostics(w.state)
        assert w.health.toPlainText() + '\n' + w.live_health.toPlainText() == unified
        assert w.health.isReadOnly() and w.live_health.isReadOnly()
        assert w.processing_health.isReadOnly()
        assert w.processing_health.accessibleName() == 'LIVE processing budget telemetry (scrollable)'
        assert w.processing_health.isVisible()
        assert w.health.accessibleName() == 'ALIVE diagnostics (scrollable)'
        assert w.live_health.accessibleName() == 'LIVE diagnostics (scrollable)'
        assert w.health.font().family() == w.live_health.font().family()
        assert w.processing_health.font().family() == w.health.font().family()
        assert 'No LIVE processor observations yet' in w.processing_health.toPlainText()
        assert 'LIVE Processing — Engine & Budget' in (
            label.text() for label in w._telemetry_panel.findChildren(type(w.file_status))
        )
        for heading in ('ALIVE — Local playback', 'Remastered stage:'):
            assert heading in w.health.toPlainText()
        assert 'LIVE — Transport' in w.live_health.toPlainText()
        assert 'No active LIVE monitoring stream.' in w.live_health.toPlainText()
    finally:
        close_window(app, w, controller)



@pytest.mark.parametrize('width', [1100, 800, 640])
def test_footer_wave_signature_stays_between_original_buttons(app, width):
    w, controller, *_ = window_session(app)
    try:
        w.resize(width, 900)
        app.processEvents()
        footer = w.centralWidget().layout().itemAt(
            w.centralWidget().layout().count() - 1
        ).layout()
        assert footer.indexOf(w.refresh) < footer.indexOf(w.wave_signature)
        assert footer.indexOf(w.wave_signature) < footer.indexOf(w.close_button)
        signature = w.wave_signature
        assert signature.isVisible()
        assert signature.objectName() == 'footerWaveSignature'
        assert signature.accessibleName() == (
            'Audio effect and playback status'
        )
        assert 'not live audio' in signature.toolTip()
        assert tuple(wave[0] for wave in signature._WAVES) == (
            'ORIGINAL', 'VELVET', 'LEGATO', 'MELT')
        assert len({wave[1] for wave in signature._WAVES}) == 4
        assert signature._wave_timer.interval() == 80
        assert not signature._wave_timer.isActive()
        assert w.timer.interval() == 50  # Original polling, unchanged.
        assert w.refresh.isVisible() and w.close_button.isVisible()
        assert w.refresh.geometry().right() < signature.geometry().left()
        assert signature.geometry().right() < w.close_button.geometry().left()
        assert not signature.grab().isNull()
        signature.hide()
        assert not signature._wave_timer.isActive()
        signature.show()
        assert not signature._wave_timer.isActive()
    finally:
        close_window(app, w, controller)



def test_footer_selection_and_motion_follow_worker_status(app):
    from isla.footer_status import FooterStatus
    w, controller, *_ = window_session(app)
    try:
        wave = w.wave_signature
        assert not wave._wave_timer.isActive()
        initial = tuple(wave._phases)
        wave._animate()
        assert tuple(wave._phases) == initial
        # Highlight the requested effect, moving only the worker-confirmed lane.
        status = FooterStatus('LIVE', 'melt', 'velvet', 'Switching', True)
        wave.set_status(status)
        assert wave._status.selected == 'melt'
        assert 'Switching' in wave.toolTip()
        before = tuple(wave._phases)
        wave._animate()
        assert wave._phases[1] != before[1]
        assert all(wave._phases[i] == before[i] for i in (0, 2, 3))
        # Repeated 50 ms status refreshes must not restart the 80 ms timer.
        w.timer.stop()
        before = tuple(wave._phases)
        for _ in range(4):
            wave.set_status(status)
            QTest.qWait(50)
        assert tuple(wave._phases) != before
        wave.hide()
        assert not wave._wave_timer.isActive()
        wave.show()
        assert wave._wave_timer.isActive()
        wave.set_status(FooterStatus('LIVE', 'melt', stage='Stopped safely'))
        frozen = tuple(wave._phases)
        wave._animate()
        assert tuple(wave._phases) == frozen
        assert not wave._wave_timer.isActive()
        assert wave._status.selected == 'melt'
    finally:
        w.timer.start()
        close_window(app, w, controller)


def test_capture_control_center_reference(app):
    directory = os.environ.get('ISLA_UI_SCREENSHOT_DIR')
    if not directory:
        pytest.skip('Screenshot capture is explicit and CI-artifact-only')
    w, controller, *_ = window_session(app)
    try:
        w.resize(1100, 950)
        app.processEvents()
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        assert w.grab().save(str(path / 'isla-control-center-blue.png'), 'PNG')
    finally:
        close_window(app, w, controller)
