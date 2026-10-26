"""Visual layout and telemetry split contract; not native audio acceptance."""
import os
from pathlib import Path

import pytest

pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtWidgets import QScrollArea

from isla.qt_window import audio_diagnostics
from test_qt_window import app, window_session, close_window


@pytest.mark.parametrize('size', [(1100, 950), (1040, 830), (800, 600), (1440, 900)])
def test_three_columns_lower_telemetry_and_research_controls(app, size):
    w, controller, *_ = window_session(app)
    try:
        w.resize(*size)
        app.processEvents()
        scroll = w.findChild(QScrollArea)
        grid = scroll.widget().layout()
        alive, remastered, live, diagnostics = (
            grid.itemAtPosition(0, 0).widget(),
            grid.itemAtPosition(0, 1).widget(),
            grid.itemAtPosition(0, 2).widget(),
            grid.itemAtPosition(1, 0).widget(),
        )
        assert [panel.title() for panel in (alive, remastered, live)] == [
            'ALIVE — Local Audio File', 'v4.0 Remastered',
            'LIVE — Mac System Audio']
        assert grid.itemAtPosition(1, 1).widget() is diagnostics
        assert grid.itemAtPosition(1, 2).widget() is live
        assert diagnostics.title() == 'Diagnostics — ALIVE / LIVE'
        assert diagnostics.geometry().top() >= alive.geometry().bottom()
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
                scroll.ensureWidgetVisible(control)
                app.processEvents()
                center = control.mapTo(scroll.viewport(), control.rect().center())
                assert scroll.viewport().rect().contains(center)
        if size == (1100, 950):
            assert scroll.horizontalScrollBar().maximum() == 0
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
