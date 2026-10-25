"""Three-column presentation and scroll reachability; no hardware acceptance."""
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtWidgets import QScrollArea
from test_qt_window import app, window_session, close_window


@pytest.mark.parametrize('size', [(1040, 830), (800, 600), (1440, 900)])
def test_columns_and_collapsed_research_keep_controls_reachable(app, size):
    w, c, *_ = window_session(app)
    try:
        w.resize(*size)
        scroll = w.findChild(QScrollArea)
        columns = scroll.widget().layout()
        panels = [columns.itemAt(i).widget() for i in range(columns.count())]
        assert [p.title() for p in panels] == [
            'ALIVE — Local Audio File', 'v4.0 Remastered', 'LIVE — Mac System Audio']
        assert panels[0].isAncestorOf(w.play)
        assert panels[1].isAncestorOf(w.research_panel)
        assert panels[1].isAncestorOf(w.save_mix_button)
        assert panels[2].isAncestorOf(w.live_engine)
        assert w.timer.interval() == 50
        for expanded in (True, False, True):
            w.research_toggle.setChecked(expanded)
            app.processEvents()
            assert w.research_panel.isVisible() == expanded
            assert w.save_mix_button.isVisible() and w.return_research.isVisible()
            assert all(a.geometry().right() < b.geometry().left()
                       for a, b in zip(panels, panels[1:]))
            for control in (w.open_file, w.apply_output, w.research_toggle,
                            w.save_mix_button, w.return_research, w.start_live,
                            w.monitor_volume, w.health):
                target = control.mapTo(scroll.widget(), control.rect().center())
                scroll.ensureVisible(target.x(), target.y())
                app.processEvents()
                center = control.mapTo(scroll.viewport(), control.rect().center())
                assert scroll.viewport().rect().contains(center)
            if size == (1040, 830):
                assert scroll.horizontalScrollBar().maximum() == 0
    finally:
        close_window(app, w, c)
