"""Local character presets and model browsing; these controls never call the API."""
from .i18n import tr
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QInputDialog, QLabel, QMessageBox, QVBoxLayout, QWidget)
from .file_dialogs import FileDialogs as QFileDialog

from .characters import CHARACTER_FIELDS, delete_character, project_file, reference_transcript, save_character, scan_models


class CharacterMixin:
    def build_character_tools(self):
        from .ui import button, hint, row
        self.character_tools = QWidget()
        layout = QVBoxLayout(self.character_tools)
        layout.setContentsMargins(0, 0, 0, 0)
        self.character_choice = QComboBox()
        self.character_choice.setMinimumContentsLength(14)
        self.character_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        layout.addWidget(row(QLabel(tr('ui.dfe54c4a2ef9', '角色预设')), self.character_choice,
            button(tr('ui.81854b085af3', '保存角色'), self.save_current_character), button(tr('ui.9016c463977d', '另存为…'), lambda: self.save_current_character(as_new=True)),
            button(tr('ui.5e7dadca706f', '删除角色'), self.delete_current_character)))
        self.model_pair_choice = QComboBox()
        self.model_pair_choice.setMinimumContentsLength(18)
        self.model_pair_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.scan_models_button = button(tr('ui.8ed248bc6e83', '扫描本地模型'), self.scan_character_models)
        layout.addWidget(row(self.scan_models_button, self.model_pair_choice))
        self.reference_choice = QComboBox()
        self.reference_choice.setMinimumContentsLength(18)
        self.reference_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        layout.addWidget(row(QLabel(tr('ui.869c4bb01829', '项目参考音频')), self.reference_choice,
            button(tr('ui.9577eebd684f', '填入参考音频'), self.choose_scanned_reference), button(tr('ui.cb26cdc97429', '读取同名原文'), self.read_reference_text)))
        self.character_status = hint(tr('ui.364a233522a2', '填写项目目录后自动只读扫描；扫描、选择、保存均不启动 API。'))
        layout.addWidget(self.character_status)
        self.character_scan_timer = QTimer(self)
        self.character_scan_timer.setSingleShot(True)
        self.character_scan_timer.setInterval(600)
        self.character_scan_timer.timeout.connect(self.scan_character_models)
        self.character_scan_serial = 0
        self.character_scan_cache = None
        self.active_character = ""
        self.character_choice.currentIndexChanged.connect(self.choose_character)
        self.model_pair_choice.currentIndexChanged.connect(self.choose_model_pair)
        return self.character_tools

    def model_path_field(self, combo):
        from .ui import button, row
        def choose():
            combo.setProperty("projectRelative",True)
            value, _ = QFileDialog.getOpenFileName(combo, tr('ui.ec9dc7848ed8', '选择本地模型权重'), combo.currentText(), tr('ui.5ebb5a47f18b', '模型 (*.ckpt *.pth)'))
            if value:
                combo.setCurrentText(value)
        return row(combo, button(tr('ui.0617557e7bbc', '浏览…'), choose))

    def character_provider_changed(self):
        visible = self.rendered_provider == "gpt_sovits"
        self.character_tools.setVisible(visible)
        self.character_scan_timer.stop()
        if not visible:
            return
        desired = self.active_character or self.store.config.get("tts_character", "")
        self.refresh_characters(desired)
        self.provider_widgets["project"].textChanged.connect(self.schedule_character_scan)
        self.schedule_character_scan()

    def refresh_characters(self, desired=""):
        self.character_choice.blockSignals(True)
        self.character_choice.clear()
        self.character_choice.addItem(tr('ui.69635161f7fc', '当前设置 / 未选角色'), "")
        for entry in self.store.config.get("tts_characters", []):
            self.character_choice.addItem(entry["name"], entry["id"])
        self.character_choice.setCurrentIndex(max(0, self.character_choice.findData(desired)))
        self.active_character = self.character_choice.currentData()
        self.character_choice.blockSignals(False)

    def schedule_character_scan(self):
        if self.rendered_provider == "gpt_sovits" and self.provider_widgets["project"].text().strip():
            project = str(Path(self.provider_widgets["project"].text()).expanduser().resolve())
            if not self.character_scan_cache or self.character_scan_cache["project"] != project:
                self.model_pair_choice.blockSignals(True)
                self.model_pair_choice.clear()
                self.model_pair_choice.addItem(tr('ui.a47c8d900532', '等待本项目扫描结果…'), None)
                self.model_pair_choice.blockSignals(False)
                self.reference_choice.clear()
            self.character_scan_timer.start()

    def scan_character_models(self):
        if self.quitting or self.rendered_provider != "gpt_sovits":
            return
        project = self.provider_widgets["project"].text().strip()
        if not project:
            self.character_status.setText(tr('ui.091a356e6125', '请先填写 GPT-SoVITS 项目目录。'))
            return
        self.character_scan_timer.stop()
        self.character_scan_serial += 1
        serial = self.character_scan_serial
        self.scan_models_button.setEnabled(False)
        self.character_status.setText(tr('ui.426aedf679f7', '正在只读扫描权重和参考音频，不启动 API…'))
        def done(result):
            if serial != self.character_scan_serial:
                return
            self.scan_models_button.setEnabled(True)
            self.character_scan_cache = result
            if self.rendered_provider != "gpt_sovits" or str(Path(self.provider_widgets["project"].text()).expanduser().resolve()) != result["project"]:
                return
            self.fill_character_models(result)
        def failed(error):
            if serial == self.character_scan_serial:
                self.scan_models_button.setEnabled(True)
                self.character_status.setText(tr('ui.3d94c1d2dcb7', '扫描未完成：') + str(error))
        self.submit(lambda: scan_models(project), done, failed)

    def fill_character_models(self, result):
        for key, kind in [("gpt_weights", "gpt"), ("sovits_weights", "sovits")]:
            combo = self.provider_widgets[key]
            value = combo.currentText()
            combo.blockSignals(True)
            combo.clear(); combo.addItem("")
            for model in result["models"]:
                if model["kind"] == kind:
                    combo.addItem(model["path"])
                    combo.setItemData(combo.count() - 1, tr('ui.9367032f0543', '版本提示：') + (model["version"] or tr('ui.ec84dd3bfc2d', '未知，请核对兼容性')), Qt.ItemDataRole.ToolTipRole)
            combo.setCurrentText(value)
            combo.blockSignals(False)
        self.model_pair_choice.blockSignals(True)
        self.model_pair_choice.clear(); self.model_pair_choice.addItem(tr('ui.60901ed14613', '选择配对候选（请核对兼容性）'), None)
        for pair in result["pairs"]:
            self.model_pair_choice.addItem(f"{pair['name']} · {pair['version'] or tr('ui.f1e7bec171ae', '未知版本')} · {Path(pair['gpt_weights']).parent}", pair)
        self.model_pair_choice.blockSignals(False)
        self.reference_choice.clear()
        self.reference_choice.addItems(result["references"])
        self.sync_scanned_character()
        self.character_status.setText(tr('ui.658bc1d34c0a', '发现 {value0} 个权重、{value1} 个唯一配对候选、{value2} 段参考音频。选择后核对原文并保存角色。', value0=len(result['models']), value1=len(result['pairs']), value2=len(result['references'])))
        self.character_status.setToolTip("\n".join(result["warnings"]))

    def sync_scanned_character(self):
        settings = self.tts_settings()
        try:
            current = (project_file(settings, "gpt_weights"), project_file(settings, "sovits_weights"))
        except (ValueError, OSError):
            current = None
        index = 0
        for row in range(1, self.model_pair_choice.count()):
            pair = self.model_pair_choice.itemData(row)
            if current == (project_file({**settings, **pair}, "gpt_weights"), project_file({**settings, **pair}, "sovits_weights")):
                index = row; break
        self.model_pair_choice.blockSignals(True)
        self.model_pair_choice.setCurrentIndex(index)
        self.model_pair_choice.blockSignals(False)
        try:
            value = project_file(settings, "reference")
            index = next((i for i in range(self.reference_choice.count())
                          if project_file({**settings, "reference": self.reference_choice.itemText(i)}, "reference") == value), -1)
            self.reference_choice.setCurrentIndex(index)
        except (ValueError, OSError):
            self.reference_choice.setCurrentIndex(-1)

    def choose_model_pair(self):
        pair = self.model_pair_choice.currentData()
        if pair and self.rendered_provider == "gpt_sovits":
            for key in ("gpt_weights", "sovits_weights"):
                self.provider_widgets[key].setCurrentText(pair[key])
            self.character_status.setText(tr('ui.dce23372302d', '已填入配对候选；参考音频、原文和语言仍需核对。尚未启动或切换模型。'))

    def choose_scanned_reference(self):
        if self.rendered_provider == "gpt_sovits" and self.reference_choice.currentText():
            self.provider_widgets["reference"].setText(self.reference_choice.currentText())

    def read_reference_text(self):
        if self.rendered_provider != "gpt_sovits":
            return
        try:
            text = reference_transcript(self.tts_settings())
            self.provider_widgets["prompt"].setPlainText(text)
            self.character_status.setText(tr('ui.9163258edc18', '已读取同名原文，请核对是否与参考音频逐字一致。'))
        except Exception as exc:
            self.report_error(str(exc))

    def choose_character(self):
        if self.rendered_provider != "gpt_sovits":
            return
        identifier = self.character_choice.currentData()
        previous = next((item for item in self.store.config.get("tts_characters", []) if item["id"] == self.active_character), None)
        if previous and identifier != self.active_character:
            current = self.tts_settings()
            if any(current.get(key, "") != previous["settings"].get(key, "") for key in CHARACTER_FIELDS):
                if QMessageBox.question(self, tr('ui.7cbecca8f822', '角色修改尚未保存'), tr('ui.1ed86ca4b3d9', '当前角色字段已修改，但尚未保存到角色预设。放弃这些修改并切换？'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    self.refresh_characters(self.active_character)
                    return
        self.active_character = identifier
        entry = next((item for item in self.store.config.get("tts_characters", []) if item["id"] == identifier), None)
        if not entry:
            return
        for key, value in entry["settings"].items():
            widget = self.provider_widgets.get(key)
            if widget is None:
                continue
            if key == "prompt":
                widget.setPlainText(value)
            elif key in {"gpt_weights", "sovits_weights"}:
                widget.setCurrentText(value)
            elif key == "speed":
                widget.setValue(value)
            else:
                widget.setText(value)
        self.sync_scanned_character()
        self.character_status.setText(tr('ui.caf6fddf880b', '已选择角色：') + entry["name"] + tr('ui.c55b67fcd430', '。选择本身不加载模型；生成或手动启动 API 时加载。'))

    def save_current_character(self, as_new=False):
        if self.rendered_provider != "gpt_sovits":
            return
        identifier = "" if as_new else self.character_choice.currentData()
        entry = next((item for item in self.store.config.get("tts_characters", []) if item["id"] == identifier), None)
        suggestion = entry["name"] if entry else (self.model_pair_choice.currentData() or {}).get("name", "")
        name, accepted = QInputDialog.getText(self, tr('ui.4e7dbcb7ca6e', '保存角色预设'), tr('ui.519006fe536c', '角色名称'), text=suggestion)
        if not accepted:
            return
        try:
            item = save_character(self.store, name, self.tts_settings(), identifier or "")
            self.refresh_characters(item["id"])
            self.character_status.setText(tr('ui.01de5cc72733', '已保存角色：') + item["name"] + tr('ui.430c4887246f', '。未启动 API，也未加载权重。'))
        except Exception as exc:
            self.report_error(str(exc))

    def delete_current_character(self):
        identifier = self.character_choice.currentData()
        if not identifier:
            return
        if QMessageBox.question(self, tr('ui.093e6a084add', '删除角色预设'), tr('ui.12f08f6558a1', '只删除这份预设，模型、参考音频和台词文件全部保留。继续？'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_character(self.store, identifier)
            self.refresh_characters()
        except Exception as exc:
            self.report_error(str(exc))
