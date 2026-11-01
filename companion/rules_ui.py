"""Progressive rule editor with focused, game-style keyboard recording."""
import copy

from PySide6.QtCore import QEvent, Qt, QTime
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGroupBox, QLabel, QLineEdit, QMessageBox, QVBoxLayout)

from .core import new_rule
from .rules import display_hotkey, qt_hotkey, validate_rule


class RuleDialog(QDialog):
    def __init__(self, rule=None, parent=None, existing_rules=()):
        from .ui import EVENTS, button, hint, path_field, row, spin
        super().__init__(parent)
        self.setWindowTitle("互动规则 · 选择触发方式")
        self.resize(670, 540)
        self.rule = copy.deepcopy(rule or new_rule())
        self.existing_rules = existing_rules
        self._recording = False
        self._modifier_candidate = None
        self._auto_name = rule is None
        self._binding = self.rule.get("hotkey", "<f8>")
        r = self.rule
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.name = QLineEdit(r["name"])
        self.name.textEdited.connect(lambda text: setattr(self, "_auto_name", False))
        self.enabled = QCheckBox("启用这条规则")
        self.enabled.setChecked(r["enabled"])
        self.trigger_category = QComboBox()
        self.trigger_category.addItem("按时间触发", "time")
        self.trigger_category.addItem("按事件触发", "event")
        self.time_mode = QComboBox()
        self.time_mode.addItem("每天固定时刻", "scheduled")
        self.time_mode.addItem("在时间段内随机播放", "random")
        self.event_family = QComboBox()
        for title, value in [("鼠标触发", "mouse"), ("键盘触发", "keyboard"), ("壁纸 / 扩展事件", "other")]:
            self.event_family.addItem(title, value)
        self.mouse_action = QComboBox()
        for key in ["mouse_left", "mouse_right", "mouse_middle", "mouse_x1", "mouse_x2", "scroll_up", "scroll_down"]:
            self.mouse_action.addItem(EVENTS.get(key, key), key)
        self.keyboard_mode = QComboBox()
        self.keyboard_mode.addItem("指定按键或组合键", "key")
        self.keyboard_mode.addItem("任意按键", "any_key")
        self.other_event = QComboBox()
        for key, title in EVENTS.items():
            if key not in {"random", "scheduled", "key", "any_key"} and not key.startswith(("mouse_", "scroll_")):
                self.other_event.addItem(title, key)
        if self.other_event.findData(r["event"]) < 0 and r["event"] not in {"random", "scheduled", "key", "any_key"} and not r["event"].startswith(("mouse_", "scroll_")):
            self.other_event.addItem("未加载扩展：" + r["event"], r["event"])
        self.hotkey = QLineEdit(display_hotkey(self._binding))
        self.hotkey.setReadOnly(True)
        self.record_button = button("录制按键", self.start_recording, True)
        self.cancel_record_button = button("取消录制", self.cancel_recording)
        self.cancel_record_button.hide()
        self.key_row = row(self.hotkey, self.record_button, self.cancel_record_button)
        self.capture_hint = hint("点击录制后按下想绑定的键或组合键，例如 Ctrl + Alt + H；Esc 取消录制。")
        self.at = self._time(r.get("at", "09:00"))
        self.start = self._time(r["start"])
        self.end = self._time(r["end"])
        self.low = spin(5, 86400, r["interval_min"], " 秒")
        self.high = spin(5, 86400, r["interval_max"], " 秒")
        self.time_window = row(self.start, QLabel("至"), self.end)
        self.interval_row = row(self.low, QLabel("至"), self.high)
        self.source_mode = QComboBox()
        for title, value in [("从语音总目录随机选取", "all"), ("选择台词分类 / 子目录", "category"), ("自选文件或文件夹", "custom")]:
            self.source_mode.addItem(title, value)
        self.source_category = QComboBox()
        self.source_category.setEditable(False)
        from .dialogues import starter_dialogues
        categories = list(dict.fromkeys(e["category"] for e in getattr(parent, "edit_dialogues", starter_dialogues())))
        from pathlib import Path
        voice_root = getattr(parent, "voice_dir", None)
        if voice_root and voice_root.text().strip():
            try:
                categories.extend(p.name for p in Path(voice_root.text()).iterdir() if p.is_dir() and p.name not in categories)
            except OSError:
                pass
        if r["source"] and not any(c in r["source"] for c in "/\\:") and r["source"] not in categories:
            categories.append(r["source"])  # Preserve a legacy category whose library is not loaded.
        self.source_category.addItems(categories)
        self.source = QLineEdit(r["source"])
        self.custom_source = row(path_field(self.source), button("选音频文件…", self.choose_file))
        self.keyword = QLineEdit(r["keyword"])
        self.keyword.setPlaceholderText("可选：只播放文件名含这些文字的音频")
        self.cooldown = spin(0, 86400, r["cooldown"], " 秒")
        for title, widget in [("规则名称", self.name), ("", self.enabled), ("① 触发分类", self.trigger_category),
                              ("时间方式", self.time_mode), ("事件分类", self.event_family), ("鼠标动作", self.mouse_action),
                              ("键盘方式", self.keyboard_mode), ("绑定按键", self.key_row), ("", self.capture_hint),
                              ("每天几点", self.at), ("播放时段", self.time_window), ("随机间隔", self.interval_row),
                              ("② 播放什么", self.source_mode), ("台词分类 / 子目录", self.source_category), ("音频来源", self.custom_source)]:
            self.form.addRow(title, widget)
        layout.addLayout(self.form)
        self.advanced = QGroupBox("更多设置（冷却、文件名筛选、事件生效时段）")
        self.advanced.setCheckable(True)
        advanced_layout = QVBoxLayout(self.advanced)
        self.advanced_contents = QGroupBox()
        advanced_form = QFormLayout(self.advanced_contents)
        self.advanced_form = advanced_form
        self.limit_window = QCheckBox("事件只在指定时间段内触发")
        self.limit_window.setChecked(r["start"] != r["end"] and r["event"] not in {"random", "scheduled"})
        self.event_start, self.event_end = self._time(r["start"]), self._time(r["end"])
        self.event_window = row(self.event_start, QLabel("至"), self.event_end)
        advanced_form.addRow("规则冷却", self.cooldown)
        advanced_form.addRow("文件名包含", self.keyword)
        advanced_form.addRow("", self.limit_window)
        advanced_form.addRow("生效时段", self.event_window)
        advanced_layout.addWidget(self.advanced_contents)
        layout.addWidget(self.advanced)
        self.advanced.toggled.connect(self.advanced_contents.setVisible)
        self.advanced.toggled.connect(lambda checked: self.advanced.setMaximumHeight(500 if checked else 36))
        expanded = bool(r["keyword"] or r["cooldown"] != 20 or self.limit_window.isChecked())
        self.advanced.setChecked(expanded)
        self.advanced_contents.setVisible(expanded)
        self.advanced.setMaximumHeight(500 if expanded else 36)
        layout.addWidget(hint("设好触发方式和播放分类即可保存。总目录/分类中需已有音频；导入台词文字后仍需合成或下载音频。"))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Save).setText("保存规则")
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        event = r["event"]
        self.trigger_category.setCurrentIndex(0 if event in {"random", "scheduled"} else 1)
        self.time_mode.setCurrentIndex(max(0, self.time_mode.findData(event)))
        family = "keyboard" if event in {"key", "any_key"} else "mouse" if event.startswith(("mouse_", "scroll_")) else "other"
        self.event_family.setCurrentIndex(self.event_family.findData(family))
        for combo in [self.mouse_action, self.keyboard_mode, self.other_event]:
            if combo.findData(event) >= 0:
                combo.setCurrentIndex(combo.findData(event))
        if r["source"]:
            simple = not any(c in r["source"] for c in "/\\:")
            self.source_mode.setCurrentIndex(1 if simple else 2)
            if simple:
                self.source_category.setCurrentText(r["source"])
        for combo in [self.trigger_category, self.time_mode, self.event_family, self.mouse_action, self.keyboard_mode, self.other_event, self.source_mode]:
            combo.currentIndexChanged.connect(self.update_fields)
        self.limit_window.toggled.connect(self.update_fields)
        QApplication.instance().installEventFilter(self)
        self.update_fields()
        from .help_ui import annotate_controls
        annotate_controls(self)

    @staticmethod
    def _time(value):
        from PySide6.QtWidgets import QTimeEdit
        widget = QTimeEdit(QTime.fromString(value, "HH:mm"))
        widget.setDisplayFormat("HH:mm")
        return widget

    def selected_event(self):
        if self.trigger_category.currentData() == "time":
            return self.time_mode.currentData()
        family = self.event_family.currentData()
        return self.mouse_action.currentData() if family == "mouse" else self.keyboard_mode.currentData() if family == "keyboard" else self.other_event.currentData()

    def update_fields(self, *args):
        timed = self.trigger_category.currentData() == "time"
        event = self.selected_event()
        family = self.event_family.currentData()
        if self._auto_name:
            title = "每天定时语音" if event == "scheduled" else "时段随机语音" if event == "random" else self.mouse_action.currentText() + "回应" if family == "mouse" else "按键回应" if family == "keyboard" else self.other_event.currentText()
            self.name.setText(title)
        rows = [(self.time_mode, timed), (self.event_family, not timed), (self.mouse_action, not timed and family == "mouse"),
                (self.keyboard_mode, not timed and family == "keyboard"), (self.key_row, event == "key"), (self.capture_hint, event == "key"),
                (self.at, event == "scheduled"), (self.time_window, event == "random"), (self.interval_row, event == "random"),
                (self.source_category, self.source_mode.currentData() == "category"), (self.custom_source, self.source_mode.currentData() == "custom")]
        for widget, visible in rows:
            self.form.setRowVisible(widget, visible)
        self.advanced_form.setRowVisible(self.limit_window, not timed)
        self.advanced_form.setRowVisible(self.event_window, not timed and self.limit_window.isChecked())
        if event != "key":
            self.cancel_recording()

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择语音文件", self.source.text(), "音频 (*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.wma *.opus);;所有文件 (*)")
        if path:
            self.source.setText(path)

    def start_recording(self):
        self._recording = True
        self._modifier_candidate = None
        self.record_button.setText("请按键…")
        self.hotkey.setText("等待按键…")
        self.cancel_record_button.show()
        self.record_button.setFocus()

    def cancel_recording(self):
        self._recording = False
        self._modifier_candidate = None
        self.record_button.setText("重新录制")
        self.cancel_record_button.hide()
        self.hotkey.setText(display_hotkey(self._binding))

    def eventFilter(self, obj, event):
        if self._recording and hasattr(obj, "window") and obj.window() is self and event.type() == QEvent.Type.KeyRelease and self._modifier_candidate:
            self._binding = self._modifier_candidate
            self.cancel_recording()
            self.capture_hint.setText("已绑定：" + display_hotkey(self._binding))
            return True
        if self._recording and hasattr(obj, "window") and obj.window() is self and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.cancel_recording()
            elif not event.isAutoRepeat():
                try:
                    binding = qt_hotkey(event)
                    if binding:
                        self._binding = binding
                        self.cancel_recording()
                        self.capture_hint.setText("已绑定：" + display_hotkey(binding))
                    else:
                        parts = ["<" + name + ">" for flag, name in [(Qt.KeyboardModifier.ControlModifier, "ctrl"), (Qt.KeyboardModifier.AltModifier, "alt"), (Qt.KeyboardModifier.ShiftModifier, "shift"), (Qt.KeyboardModifier.MetaModifier, "cmd")] if event.modifiers() & flag]
                        self._modifier_candidate = "+".join(parts) or None
                except ValueError as exc:
                    self.capture_hint.setText(str(exc))
            return True
        return False

    def reject(self):
        self.cancel_recording()
        super().reject()

    def accept(self):
        try:
            if self._recording:
                raise ValueError("请先完成按键绑定，或取消录制")
            event = self.selected_event()
            source_mode = self.source_mode.currentData()
            source = self.source_category.currentText().strip() if source_mode == "category" else self.source.text().strip() if source_mode == "custom" else ""
            if source_mode == "category":
                from .presets import relative_source
                if not source:
                    raise ValueError("请先在台词库添加分类，或选择自选文件/文件夹")
                source = relative_source(source)
            start = end = "00:00"
            if event == "random":
                start, end = self.start.time().toString("HH:mm"), self.end.time().toString("HH:mm")
            elif event != "scheduled" and self.limit_window.isChecked():
                start, end = self.event_start.time().toString("HH:mm"), self.event_end.time().toString("HH:mm")
            updated = {**self.rule, "name": self.name.text().strip(), "enabled": self.enabled.isChecked(), "event": event,
                       "hotkey": self._binding, "source": source, "keyword": self.keyword.text().strip(), "start": start, "end": end,
                       "at": self.at.time().toString("HH:mm"), "cooldown": self.cooldown.value(),
                       "interval_min": self.low.value(), "interval_max": self.high.value()}
            validate_rule(updated)
            if updated["enabled"] and event == "key":
                from pynput.keyboard import HotKey
                keys = set(HotKey.parse(self._binding))
                if any(r["id"] != updated["id"] and r.get("enabled", True) and r.get("event") == "key" and set(HotKey.parse(r.get("hotkey", ""))) == keys for r in self.existing_rules):
                    raise ValueError("此按键已被另一条启用规则使用，请录制其他按键或先停用原规则")
            self.rule = updated
        except ValueError as exc:
            QMessageBox.warning(self, "请检查规则", str(exc))
            return
        self.cancel_recording()
        super().accept()
