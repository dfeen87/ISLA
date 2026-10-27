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
            'ALIVE — Local Audio File', 'v4.0 Remastered',
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
        assert w.timer.interval() == 50

        for expanded in (False, True, False):
            w.research_toggle.setChecked(expanded)
            app.processEvents()
            assert w.research_panel.isVisible() == expanded
            assert all(widget.isVisible() for widget in (
                w.save_mix_button, w.cancel_research, w.return_research,
                w.health, w.live_health, w.monitor_volume, w.mute_volume))
            for control in (
                w.open_file, w.play, w.pause, w.stop_file,
                w.alive_volume, w.file_output, w.apply_output,
                *w.file_modes.values(), w.research_toggle,
                w.save_mix_button, w.cancel_research, w.return_research,
                w.capture, w.output, w.rate, w.apply_devices, w.settings,
                w.recheck, w.start_live, w.stop_live, w.live_engine,
                w.live_intensity, w.apply_live_intensity,
                w.live_mode_choice, w.reset_live_mode, w.monitor_volume,
                w.mute_volume, w.health, w.live_health,
            ) + ((w.enter_research, w.research_mode, w.research_intensity,
                  w.apply_research) if expanded else ()):
                assert control.parentWidget().rect().contains(control.geometry())
                if hasattr(control, 'text') and control.text():
                    assert control.width() >= control.minimumSizeHint().width()
                # Qt's ensureVisible() can position the target *on* the
                # viewport's lower edge when margins are zero (y == height,
                # which is outside QRect.contains). Reserve an explicit
                # 12-pixel visibility margin without weakening reachability.
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
            *w.file_modes.values(), w.apply_output, w.research_toggle,
            w.save_mix_button, w.cancel_research, w.return_research,
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


def test_split_telemetry_retains_every_original_diagnostic_line(app):
    w, controller, *_ = window_session(app)
    try:
        app.processEvents()
        # No parsing, reformatting, deleted counters or redacted failure states.
        unified = audio_diagnostics(w.state)
        assert w.health.toPlainText() + '\n' + w.live_health.toPlainText() == unified
        assert w.health.isReadOnly() and w.live_health.isReadOnly()
        assert w.health.accessibleName() == 'ALIVE diagnostics (scrollable)'
        assert w.live_health.accessibleName() == 'LIVE diagnostics (scrollable)'
        assert w.health.font().family() == w.live_health.font().family()
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
            'Decorative Velvet, Legato, and Melt waveform signature'
        )
        assert 'not live audio' in signature.toolTip()
        assert tuple(wave[0] for wave in signature._WAVES) == (
            'VELVET', 'LEGATO', 'MELT')
        assert len({wave[1] for wave in signature._WAVES}) == 3
        assert signature._wave_timer.interval() == 80
        assert signature._wave_timer.isActive()
        assert w.timer.interval() == 50  # Original polling, unchanged.
        assert w.refresh.isVisible() and w.close_button.isVisible()
        assert w.refresh.geometry().right() < signature.geometry().left()
        assert signature.geometry().right() < w.close_button.geometry().left()
        assert not signature.grab().isNull()
        signature.hide()
        assert not signature._wave_timer.isActive()
        signature.show()
        assert signature._wave_timer.isActive()
    finally:
        close_window(app, w, controller)



def test_footer_wave_follows_applied_telemetry_not_requested_mode(app):
    w, controller, *_ = window_session(app)
    prior = w.state
    try:
        wave = w.wave_signature
        assert footer_visual_mode(None) == 'overview'
        assert wave._visual_mode == 'overview'
        initial = tuple(wave._phases)
        wave._animate()
        assert all(new != old for old, new in zip(initial, wave._phases))

        # Inactive selections (including an ALIVE mode already selected)
        # preserve the default three-wave motion.
        idle_selected = replace(prior, file_mode='melt',
                                alive_applied_mode='melt')
        # During real playback the wave follows callback-applied, not the
        # requested mode. No callback confirmation => no effect highlight.
        cases = (
            (idle_selected, 'overview'),
            (replace(prior, file_state=UIState.PLAYING, file_mode='melt',
                     alive_applied_mode='previous buffer — selected mode awaits callback'),
             'bypass'),
            (replace(prior, file_state=UIState.PLAYING, file_mode='melt',
                     alive_applied_mode='legato'), 'legato'),
            (replace(prior, file_state=UIState.PLAYING,
                     alive_applied_mode='remastered_velvet — crossfading'),
             'velvet'),
            (replace(prior, file_state=UIState.PLAYING,
                     alive_applied_mode='original'), 'bypass'),
            (replace(prior, file_state=UIState.PAUSED,
                     alive_applied_mode='melt'), 'overview'),
            (replace(prior, live_active=True, live_state=UIState.LIVE_RUNNING,
                     live_mode='melt', live_applied_mode='velvet'), 'velvet'),
            (replace(prior, live_active=True, live_state=UIState.LIVE_RUNNING,
                     live_mode='melt', live_applied_mode=None), 'bypass'),
            (replace(prior, live_active=True, live_state=UIState.LIVE_STOPPING,
                     live_applied_mode='melt'), 'bypass'),
        )
        for state, expected in cases:
            assert footer_visual_mode(state) == expected
            w.state = state
            w.apply_state()
            assert wave._visual_mode == expected

        # Freeze truly means no phase advancement for either inactive lane;
        # selecting a new mode resumes only that lane without jumping.
        wave.set_visual_mode('melt')
        before = tuple(wave._phases)
        wave._animate()
        assert wave._phases[0] == before[0]
        assert wave._phases[1] == before[1]
        assert wave._phases[2] != before[2]
        wave.set_visual_mode('bypass')
        frozen = tuple(wave._phases)
        wave._animate()
        assert tuple(wave._phases) == frozen
        assert not wave._wave_timer.isActive()
        wave.set_visual_mode('overview')
        assert wave._wave_timer.isActive()
        assert wave.isVisible()
    finally:
        w.state = prior
        w.apply_state()
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
