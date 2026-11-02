"""Immediate action acknowledgement; completion/errors remain operation-specific."""
from .i18n import tr
import weakref
import shiboken6
from PySide6.QtCore import QObject, QEvent, QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication, QAbstractButton, QLabel, QSizePolicy


class ActionFeedback(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.closed = False
        # Keep wrappers for C++-created dialog buttons alive until QObject death.
        self.buttons = {}
        self.label = QLabel(tr('ui.a6c5146d7f6f', '操作提示会显示在这里。'))
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.label.setMinimumWidth(0)
        window.statusBar().addWidget(self.label, 1)
        self.toast = QLabel(window, Qt.WindowType.ToolTip)
        self.toast.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.toast.setStyleSheet("QLabel { background:#322a39; color:#fff5fa; border:1px solid #67566f; border-radius:8px; padding:8px 14px; }")
        self.timer = QTimer(self); self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.toast.hide)
        QApplication.instance().installEventFilter(self)
        for button in window.findChildren(QAbstractButton):
            self.attach(button)

    def attach(self, button):
        parent = button
        while parent is not None and parent is not self.window:
            parent = parent.parentWidget()
        if parent is None or id(button) in self.buttons:
            return
        key = id(button)
        self.buttons[key] = button
        button.destroyed.connect(lambda *_: self.buttons.pop(key, None))
        reference = weakref.ref(button)
        def pressed():
            item = reference()
            if item is not None and shiboken6.isValid(item):
                title = item.text().replace("&", "").strip() or item.accessibleName() or item.toolTip() or tr('ui.0e9879fd8345', '控件')
                self.show_message(tr('ui.50fd2336f6aa', '已按下：') + title, item)
        button.pressed.connect(pressed)

    def show_message(self, text, origin=None):
        if self.closed or not self.window.isVisible():
            return
        text = str(text)
        self.label.setToolTip(text)
        self.label.setText(self.label.fontMetrics().elidedText(text.replace("\n", " "), Qt.TextElideMode.ElideRight, max(300, self.label.width())))
        if origin is not None:
            owner = origin.window()
            self.toast.setText(self.toast.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, min(650, max(220, owner.width()-40))))
            self.toast.adjustSize()
            point = owner.mapToGlobal(QPoint(owner.width()//2, owner.height()-45))
            screen = owner.screen().availableGeometry()
            x = max(screen.left(), min(point.x()-self.toast.width()//2, screen.right()-self.toast.width()))
            y = max(screen.top(), min(point.y()-self.toast.height(), screen.bottom()-self.toast.height()))
            self.toast.move(x, y); self.toast.show(); self.timer.start(1600)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Polish, QEvent.Type.Show) and isinstance(obj, QAbstractButton):
            self.attach(obj)
        if obj is self.window and event.type() == QEvent.Type.Hide:
            self.toast.hide(); self.timer.stop()
        return False

    def close(self):
        self.closed = True
        QApplication.instance().removeEventFilter(self)
        self.timer.stop(); self.toast.hide()
        self.buttons.clear()
