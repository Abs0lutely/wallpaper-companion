"""Dedicated, importable operation speech rules without editing wallpaper rules."""
from .i18n import tr
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QHeaderView, QLabel, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout)
from .file_dialogs import FileDialogs as QFileDialog
from .action_lines import EVENT_LINES
from .core import writable_path
from .operation_rules import FORMAT, config_payload, default_rules, normalize_payload


class OperationRulesDialog(QDialog):
    def __init__(self, window):
        from .ui import button, row
        super().__init__(window)
        self.w = window
        self.setWindowTitle(tr('ui.f0a282851953', '操作回应规则（独立于壁纸规则）'))
        self.resize(780,650)
        layout = QVBoxLayout(self)
        description = QLabel(tr('ui.483fb30a0e10', '控制软件内的操作回应，不改变鼠标/按键触发的壁纸规则。只播放已有音频，不启动 API。'))
        description.setWordWrap(True)
        layout.addWidget(description)
        self.enabled = QCheckBox(tr('ui.e240e062890d', '启用操作回应语音（默认开启）'))
        self.gap = QDoubleSpinBox(); self.gap.setRange(.25,60); self.gap.setSuffix(tr('ui.00fe8dda1fd7', ' 秒'))
        layout.addWidget(row(self.enabled,QLabel(tr('ui.c1fa24ed3d47', '全局最短间隔')),self.gap))
        self.locale_choice=QComboBox()
        for label,code in [("中文","zh-CN"),("日本語","ja-JP"),("English","en-US")]:self.locale_choice.addItem(label,code)
        layout.addWidget(row(self.locale_choice,button(tr("voices.switch", "快速切换分类"),self.switch_categories)))
        self.switch_status=QLabel();self.switch_status.setWordWrap(True);layout.addWidget(self.switch_status)
        self.table = QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels([tr('ui.f4f0ead1116b', '启用'),tr('ui.f101493303aa', '软件操作'),tr('ui.a3e907e85b05', '播放分类'),tr('ui.e9c46f8ea152', '该动作冷却')])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        layout.addWidget(row(button(tr('ui.bc67c1f4d88b', '导入操作规则…'),self.import_rules),button(tr('ui.d33574372187', '导出操作规则…'),self.export_rules),button(tr('ui.fd6d7b6442b5', '恢复默认操作规则'),lambda:self.load(dict(format=FORMAT,version=1,enabled=True,rules=default_rules())))))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept); controls.rejected.connect(self.reject); layout.addWidget(controls)
        self.load(config_payload(window.store.config))

    def switch_categories(self):
        from .voice_locales import switch_operation_categories
        payload=self.values()
        payload["rules"],count=switch_operation_categories(payload["rules"],self.locale_choice.currentData())
        self.load(payload)
        self.switch_status.setText(tr("voices.switched", "已更新 {count} 项默认分类；自定义分类、开关和冷却保留，保存后生效。",count=count))

    def load(self,payload):
        self.payload = normalize_payload(payload)
        self.enabled.setChecked(self.payload["enabled"]); self.gap.setValue(self.payload["min_interval"])
        self.table.setRowCount(len(self.payload["rules"]))
        from .voice_locales import category_for, LOCALES
        categories = list(dict.fromkeys([*(category_for(v[0],locale) for v in EVENT_LINES.values() for locale in LOCALES),*(v[0] for v in EVENT_LINES.values()),*(e["category"] for e in self.w.edit_dialogues),*(r["category"] for r in self.payload["rules"])]))
        for i,rule in enumerate(self.payload["rules"]):
            check=QTableWidgetItem(); check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked if rule["enabled"] else Qt.CheckState.Unchecked)
            self.table.setItem(i,0,check)
            label=QTableWidgetItem(tr("operation." + rule["event"], EVENT_LINES[rule["event"]][0].removeprefix("操作·"))); label.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i,1,label)
            combo=QComboBox(); combo.addItems(categories); combo.setCurrentText(rule["category"]); self.table.setCellWidget(i,2,combo)
            cooldown=QDoubleSpinBox(); cooldown.setRange(0,3600); cooldown.setSuffix(tr('ui.00fe8dda1fd7', ' 秒')); cooldown.setValue(rule["cooldown"]); self.table.setCellWidget(i,3,cooldown)

    def values(self):
        rules=[dict(event=r["event"],enabled=self.table.item(i,0).checkState()==Qt.CheckState.Checked,
                    category=self.table.cellWidget(i,2).currentText(),cooldown=self.table.cellWidget(i,3).value()) for i,r in enumerate(self.payload["rules"])]
        return normalize_payload(dict(format=FORMAT,version=1,enabled=self.enabled.isChecked(),min_interval=self.gap.value(),rules=rules))

    def import_rules(self):
        path,_=QFileDialog.getOpenFileName(self,tr('ui.64d61b2ae526', '导入操作回应规则'),"","JSON (*.json)")
        if path:
            try: self.load(json.loads(Path(path).read_text(encoding="utf-8-sig")))
            except (OSError,ValueError) as exc: QMessageBox.warning(self,tr('ui.4ab629b17396', '导入未完成'),str(exc))

    def export_rules(self):
        path,_=QFileDialog.getSaveFileName(self,tr('ui.9246073eb742', '导出操作回应规则'),"operation-voice-rules.json","JSON (*.json)")
        if path:
            try: writable_path(path,self.w.store.protected()).write_text(json.dumps(self.values(),ensure_ascii=False,indent=2),encoding="utf-8")
            except (OSError,ValueError) as exc: QMessageBox.warning(self,tr('ui.908621d63bdf', '导出未完成'),str(exc))

    def accept(self):
        try: self.result_payload=self.values()
        except ValueError as exc:
            QMessageBox.warning(self,tr('ui.2b7003c21eb6', '规则无效'),str(exc)); return
        super().accept()
