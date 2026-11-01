"""Dedicated, importable operation speech rules without editing wallpaper rules."""
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QHeaderView, QLabel, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout)
from .action_lines import EVENT_LINES
from .core import writable_path
from .operation_rules import FORMAT, config_payload, default_rules, normalize_payload


class OperationRulesDialog(QDialog):
    def __init__(self, window):
        from .ui import button, row
        super().__init__(window)
        self.w = window
        self.setWindowTitle("操作回应规则（独立于壁纸规则）")
        self.resize(780,650)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("控制软件内的操作回应，不改变鼠标/按键触发的壁纸规则。只播放已有音频，不启动 API。"))
        self.enabled = QCheckBox("启用操作回应语音（默认开启）")
        self.gap = QDoubleSpinBox(); self.gap.setRange(.25,60); self.gap.setSuffix(" 秒")
        layout.addWidget(row(self.enabled,QLabel("全局最短间隔"),self.gap))
        self.table = QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(["启用","软件操作","播放分类","该动作冷却"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        layout.addWidget(row(button("导入操作规则…",self.import_rules),button("导出操作规则…",self.export_rules),button("恢复默认操作规则",lambda:self.load(dict(format=FORMAT,version=1,enabled=True,rules=default_rules())))))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept); controls.rejected.connect(self.reject); layout.addWidget(controls)
        self.load(config_payload(window.store.config))

    def load(self,payload):
        self.payload = normalize_payload(payload)
        self.enabled.setChecked(self.payload["enabled"]); self.gap.setValue(self.payload["min_interval"])
        self.table.setRowCount(len(self.payload["rules"]))
        categories = list(dict.fromkeys([*(v[0] for v in EVENT_LINES.values()),*(e["category"] for e in self.w.edit_dialogues),*(r["category"] for r in self.payload["rules"])]))
        for i,rule in enumerate(self.payload["rules"]):
            check=QTableWidgetItem(); check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked if rule["enabled"] else Qt.CheckState.Unchecked)
            self.table.setItem(i,0,check)
            label=QTableWidgetItem(EVENT_LINES[rule["event"]][0].removeprefix("操作·")); label.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i,1,label)
            combo=QComboBox(); combo.addItems(categories); combo.setCurrentText(rule["category"]); self.table.setCellWidget(i,2,combo)
            cooldown=QDoubleSpinBox(); cooldown.setRange(0,3600); cooldown.setSuffix(" 秒"); cooldown.setValue(rule["cooldown"]); self.table.setCellWidget(i,3,cooldown)

    def values(self):
        rules=[dict(event=r["event"],enabled=self.table.item(i,0).checkState()==Qt.CheckState.Checked,
                    category=self.table.cellWidget(i,2).currentText(),cooldown=self.table.cellWidget(i,3).value()) for i,r in enumerate(self.payload["rules"])]
        return normalize_payload(dict(format=FORMAT,version=1,enabled=self.enabled.isChecked(),min_interval=self.gap.value(),rules=rules))

    def import_rules(self):
        path,_=QFileDialog.getOpenFileName(self,"导入操作回应规则","","JSON (*.json)")
        if path:
            try: self.load(json.loads(Path(path).read_text(encoding="utf-8-sig")))
            except (OSError,ValueError) as exc: QMessageBox.warning(self,"导入未完成",str(exc))

    def export_rules(self):
        path,_=QFileDialog.getSaveFileName(self,"导出操作回应规则","operation-voice-rules.json","JSON (*.json)")
        if path:
            try: writable_path(path,self.w.store.protected()).write_text(json.dumps(self.values(),ensure_ascii=False,indent=2),encoding="utf-8")
            except (OSError,ValueError) as exc: QMessageBox.warning(self,"导出未完成",str(exc))

    def accept(self):
        try: self.result_payload=self.values()
        except ValueError as exc:
            QMessageBox.warning(self,"规则无效",str(exc)); return
        super().accept()
