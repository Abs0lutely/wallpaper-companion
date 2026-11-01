"""A checkbox column whose mouse clicks do not race row selection updates."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget


class DialogueTable(QTableWidget):
    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        self.checkbox_press = event.button() == Qt.MouseButton.LeftButton and index.isValid() and index.column() == 0
        if self.checkbox_press:
            item = self.item(index.row(), 0)
            item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, "checkbox_press", False):
            self.checkbox_press = False
            event.accept()
            return
        super().mouseReleaseEvent(event)
