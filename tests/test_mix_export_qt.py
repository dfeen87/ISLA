"""Real offscreen Qt Save Mix controls, backed by a fake audio device."""
from dataclasses import replace

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtWidgets import QFileDialog

from test_qt_window import app, window_session, close_window, click, wait_ui
from test_control import prepared_buffers


def test_save_mix_button_exports_selected_mode_and_preserves_source(app, monkeypatch, tmp_path):
    w, c, _, files, *_ = window_session(app)
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName',
                            lambda *args: (str(tmp_path / 'purchased.m4a'), ''))
        click(app, w, w.open_file)
        c.job.result = prepared_buffers(), 48000
        wait_ui(app, lambda: w.state.can_play)
        click(app, w, w.file_modes['velvet'])
        assert c.player.mode == 'velvet'
        click(app, w, w.research_toggle)
        assert w.save_mix_button.isEnabled()
        target = tmp_path / 'my-velvet.wav'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName',
                            lambda *args: (str(target), '32-bit float WAV (*.wav)'))
        click(app, w, w.save_mix_button)
        wait_ui(app, lambda: w.state.saved_path == str(target), timeout=10)
        audio, rate = sf.read(str(target), dtype='float32', always_2d=True)
        assert rate == 48000
        np.testing.assert_array_equal(audio, c.player.buffers['velvet'])
        assert 'Saved velvet mix' in w.export_status.text()
        assert not w.state.save_pending
        assert not w.export_progress.isVisible()
        assert not files.streams  # Export must not open/start a playback device.
    finally:
        close_window(app, w, c)


def test_save_and_cancel_have_clear_independent_states(app):
    w, c, *_ = window_session(app)
    try:
        w.state = replace(w.state, can_play=True, source='file',
                          save_pending=True, save_status='Saving velvet mix…',
                          save_mode='velvet')
        w.apply_state()
        assert not w.save_mix_button.isEnabled()
        assert w.cancel_research.isEnabled()
        assert w.cancel_research.text() == 'Cancel Save'
        assert w.export_progress.minimum() == w.export_progress.maximum() == 0
        assert 'Saving velvet' in w.export_status.text()

        w.state = replace(w.state, save_pending=False, research_pending=True,
                          save_status='Mix save canceled; no destination file created.')
        w.apply_state()
        assert w.cancel_research.text() == 'Cancel Preparation'
        assert w.cancel_research.isEnabled()
        assert not w.save_mix_button.isEnabled()
        assert 'canceled' in w.export_status.text()
    finally:
        close_window(app, w, c)
