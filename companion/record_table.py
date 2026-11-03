"""Record-backed tables: allocate cells only when Qt asks to display them."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QTableView


class RecordModel(QAbstractTableModel):
    def __init__(self, columns, parent):
        super().__init__(parent)
        self.columns = columns
        self.records = []
        self.headers = [""] * columns
        self.tips = [""] * columns
        self.checked = set()
        self.key = None
        self.value = None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.columns

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.records):
            return None
        record = self.records[index.row()]
        if self.key and index.column() == 0:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if self.key(record) in self.checked else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.UserRole:
                return self.key(record)
        return self.value(record, index.column(), role) if self.value else None

    def flags(self, index):
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self.key and index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if self.key and index.isValid() and index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            key = self.key(self.records[index.row()])
            if value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value):
                self.checked.add(key)
            else:
                self.checked.discard(key)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.headers[section]
            if role == Qt.ItemDataRole.ToolTipRole:
                return self.tips[section]
        elif role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return None


class Cell:
    """Ephemeral adapter for existing host actions and hover help."""
    def __init__(self, model, row, column):
        self.model, self.row_number, self.column_number = model, row, column

    def data(self, role):
        return self.model.data(self.model.index(self.row_number, self.column_number), role)

    def text(self):
        return self.data(Qt.ItemDataRole.DisplayRole) or ""

    def toolTip(self):
        return self.data(Qt.ItemDataRole.ToolTipRole) or ""

    def checkState(self):
        return self.data(Qt.ItemDataRole.CheckStateRole)

    def setCheckState(self, state):
        self.model.setData(self.model.index(self.row_number, self.column_number), state, Qt.ItemDataRole.CheckStateRole)


class HeaderCell:
    def __init__(self, model, column):
        self.model, self.column = model, column

    def setToolTip(self, text):
        self.model.tips[self.column] = text

    def toolTip(self):
        return self.model.tips[self.column]


class RecordTable(QTableView):
    cellDoubleClicked = Signal(int, int)

    def __init__(self, rows, columns, parent=None):
        super().__init__(parent)
        self.records_model = RecordModel(columns, self)
        self.setModel(self.records_model)
        self.doubleClicked.connect(lambda index: self.cellDoubleClicked.emit(index.row(), index.column()))
        self.horizontalHeader().setResizeContentsPrecision(100)

    def set_records(self, records, value, key=None):
        model = self.records_model
        def identity(record):
            return key(record) if key else record.get("path")
        selected = {identity(model.records[index.row()]) for index in self.selectionModel().selectedRows()}
        current = self.currentIndex().row()
        current_key = identity(model.records[current]) if 0 <= current < len(model.records) else None
        model.beginResetModel()
        model.records, model.value, model.key = records, value, key
        model.checked.intersection_update(key(r) for r in records) if key else model.checked.clear()
        model.endResetModel()
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        selection = QItemSelection()
        for row, record in enumerate(records):
            if identity(record) in selected:
                selection.select(model.index(row, 0), model.index(row, model.columns-1))
            if current_key is not None and identity(record) == current_key:
                self.selectionModel().setCurrentIndex(model.index(row, 0), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    def visualItemRect(self, item):
        return self.visualRect(self.model().index(item.row_number, item.column_number))

    def rowCount(self):
        return self.records_model.rowCount()

    def currentRow(self):
        return self.currentIndex().row()

    def item(self, row, column):
        return Cell(self.records_model, row, column) if 0 <= row < self.rowCount() else None

    def setHorizontalHeaderLabels(self, labels):
        self.records_model.headers = labels

    def horizontalHeaderItem(self, column):
        return HeaderCell(self.records_model, column)
