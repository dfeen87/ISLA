"""Accessible, keyboard-operable sliding switch for optional ALIVE speed."""
from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox


class SpeedSwitch(QCheckBox):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setTristate(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position = 0.0
        self._target = False
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(140)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide.valueChanged.connect(self._slide_frame)
        self.toggled.connect(self._animate_to)

    def sizeHint(self):
        return QSize(58 + self.fontMetrics().horizontalAdvance(self.text()), 34)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, point):
        return self.rect().contains(point)

    def sync_checked(self, checked):
        blocked = self.blockSignals(True)
        try:
            self.setChecked(checked)
        finally:
            self.blockSignals(blocked)
        self._animate_to(checked)

    def _slide_frame(self, value):
        self._position = float(value)
        self.update()

    def _animate_to(self, checked):
        checked = bool(checked)
        if checked == self._target and self._position == float(checked):
            return
        if checked == self._target and self._slide.state() == QVariantAnimation.State.Running:
            return
        self._target = checked
        self._slide.stop()
        if not self.isVisible():
            self._slide_frame(float(checked))
            return
        self._slide.setStartValue(self._position)
        self._slide.setEndValue(float(checked))
        self._slide.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        top = (self.height() - 24) / 2
        track = QRectF(2, top, 42, 24)
        color = '#2F80ED' if self.isChecked() else '#A7B5C7'
        if not self.isEnabled():
            color = '#ACBDD3' if self.isChecked() else '#D6DEE8'
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(track, 12, 12)
        painter.setBrush(QColor('#FFFFFF'))
        painter.drawEllipse(QRectF(5 + 18*self._position, top+3, 18, 18))
        painter.setPen(QColor('#1E3650' if self.isEnabled() else '#8995A5'))
        painter.drawText(QRectF(54, 0, self.width()-54, self.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.text())
        if self.hasFocus():
            pen = QPen(QColor('#2F80ED'), 1, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 6, 6)
        painter.end()
