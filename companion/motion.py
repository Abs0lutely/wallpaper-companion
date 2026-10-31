"""Interruptible press/rebound effects; never animate widget/layout geometry."""
from PySide6.QtCore import QObject, QEvent, Property, QPropertyAnimation, QEasingCurve, QAbstractAnimation, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QAbstractButton, QGraphicsEffect
import shiboken6


class ButtonScaleEffect(QGraphicsEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = 1.0

    def get_scale(self):
        return self._scale

    def set_scale(self, value):
        self._scale = max(.9, min(1.04, float(value)))
        self.update()

    scale = Property(float, get_scale, set_scale)

    def boundingRectFor(self, rect):
        return rect.adjusted(-rect.width()*.025, -rect.height()*.025, rect.width()*.025, rect.height()*.025)

    def draw(self, painter):
        center = self.sourceBoundingRect(Qt.CoordinateSystem.LogicalCoordinates).center()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(center); painter.scale(self._scale, self._scale); painter.translate(-center)
        self.drawSource(painter)
        painter.restore()


class ButtonSpring(QObject):
    def __init__(self, button):
        super().__init__(button)
        self.button = button
        self.disposed = False
        self.effect = ButtonScaleEffect(button)
        button.setGraphicsEffect(self.effect)
        self.effect.setEnabled(False)
        self.pending_release = False
        self.press = QPropertyAnimation(self.effect, b"scale", self)
        self.press.setDuration(90); self.press.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.rebound = QPropertyAnimation(self.effect, b"scale", self)
        self.rebound.setDuration(360)
        curve = QEasingCurve(QEasingCurve.Type.OutBack); curve.setOvershoot(1.5)
        self.rebound.setEasingCurve(curve)
        self.press.finished.connect(self.press_finished)
        self.rebound.finished.connect(self.reset)
        button.pressed.connect(self.down)
        button.released.connect(self.up)

    def down(self):
        if self.disposed:
            return
        self.pending_release = False
        self.press.stop(); self.rebound.stop(); self.effect.setEnabled(True)
        self.press.setStartValue(self.effect.get_scale()); self.press.setEndValue(.965); self.press.start()

    def up(self):
        if self.disposed:
            return
        self.pending_release = True
        # A fast click still completes a short compression before rebounding.
        if self.press.state() != QAbstractAnimation.State.Running:
            self.press_finished()

    def press_finished(self):
        if self.pending_release:
            self.pending_release = False
            self.rebound.stop()
            self.rebound.setStartValue(self.effect.get_scale()); self.rebound.setEndValue(1.0)
            self.rebound.start()

    def reset(self):
        self.press.stop(); self.rebound.stop(); self.pending_release = False
        if shiboken6.isValid(self.effect):
            self.effect.set_scale(1.0); self.effect.setEnabled(False)


class ButtonMotion(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.springs = {}
        QApplication.instance().installEventFilter(self)
        for button in window.findChildren(QAbstractButton):
            self.attach(button)

    def attach(self, button):
        parent = button
        while parent is not None and parent is not self.window:
            parent = parent.parentWidget()
        key = id(button)
        if parent is None or key in self.springs or button.graphicsEffect() is not None:
            return
        self.springs[key] = ButtonSpring(button)
        button.destroyed.connect(lambda *_: self.springs.pop(key, None))

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind in (QEvent.Type.Polish, QEvent.Type.Show) and isinstance(obj, QAbstractButton):
            self.attach(obj)
        spring = self.springs.get(id(obj))
        if spring and kind == QEvent.Type.Hide:
            spring.reset()
        elif spring and kind == QEvent.Type.EnabledChange and not obj.isEnabled():
            spring.up()
        if obj is self.window and kind in (QEvent.Type.Hide, QEvent.Type.WindowDeactivate):
            for spring in tuple(self.springs.values()):
                spring.reset()
        return False

    def close(self):
        QApplication.instance().removeEventFilter(self)
        for spring in tuple(self.springs.values()):
            spring.disposed = True
            spring.reset()
        self.springs.clear()
