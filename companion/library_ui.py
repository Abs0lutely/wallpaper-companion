"""Library and dialogue widgets, kept separate from the host window."""
import copy
import json
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .core import identity, writable_path
from .dialogues import CATEGORIES, dialogue_rules, normalize_dialogues, starter_dialogues
from .library import apply_bindings


class BatchBindDialog(QDialog):
    def __init__(self, profiles, count, selected=None, parent=None):
        from .ui import hint, path_field, row
        super().__init__(parent)
        self.setWindowTitle("批量绑定壁纸")
        self.resize(650, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(hint(f"已勾选 {count} 张壁纸。已有绑定默认跳过；只有勾选更新才替换其音频目录，现有名称和规则仍保留。"))
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem("共用语音 / BGM 目录", "shared")
        self.mode.addItem("共用完整资源目录（含台词库）", "shared_root")
        self.mode.addItem("为每张壁纸建立独立目录", "separate")
        self.asset = QLineEdit(selected.get("asset_dir", "") if selected else "")
        if parent is not None and hasattr(parent, "store"):
            from .assets import shared_root
            self.asset.setText(str(shared_root(parent.store)))
        self.voice = QLineEdit(selected.get("voice_dir", "") if selected else "")
        self.bgm = QLineEdit(selected.get("bgm_dir", "") if selected else "")
        self.template = QComboBox()
        self.template.addItem("默认设置和规则", "")
        for profile in profiles:
            self.template.addItem(profile["name"], profile["id"])
        if selected:
            self.template.setCurrentIndex(max(0, self.template.findData(selected["id"])))
        self.update_existing = QCheckBox("同时更新已有配置的资源目录绑定")
        self.update_existing.setChecked(False)
        form.addRow("目录方式", self.mode)
        form.addRow("共享资源根目录", path_field(self.asset))
        form.addRow("语音目录", path_field(self.voice))
        form.addRow("BGM 目录（可空）", path_field(self.bgm))
        form.addRow("新配置模板", self.template)
        form.addRow("已有绑定", self.update_existing)
        layout.addLayout(form)
        layout.addWidget(hint("共享模式无需为每张壁纸重复生成语音。独立模式的目录只建立在声伴自身数据目录中，不改动壁纸文件。模板只用于新绑定。"))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        self.mode.currentIndexChanged.connect(self.update_mode)
        self.mode.setCurrentIndex(1)
        self.update_mode()

    def update_mode(self):
        self.voice.setEnabled(self.mode.currentData() == "shared")
        self.bgm.setEnabled(self.mode.currentData() == "shared")
        self.asset.setEnabled(self.mode.currentData() == "shared_root")

    def options(self):
        return dict(mode=self.mode.currentData(), voice_dir=self.voice.text().strip(), bgm_dir=self.bgm.text().strip(),
                    asset_dir=self.asset.text().strip(), template_id=self.template.currentData(), update_existing=self.update_existing.isChecked())

    def accept(self):
        if self.mode.currentData() == "shared_root" and not self.asset.text().strip():
            QMessageBox.warning(self, "请选择根目录", "共享完整资源需要选择根目录。")
            return
        if self.mode.currentData() == "shared":
            if not self.voice.text().strip() or not Path(self.voice.text().strip()).is_dir():
                QMessageBox.warning(self, "请检查目录", "共享模式需要选择已存在的语音目录。")
                return
            if self.bgm.text().strip() and not Path(self.bgm.text().strip()).is_dir():
                QMessageBox.warning(self, "请检查目录", "BGM 目录不存在。")
                return
        super().accept()


class DialogueDialog(QDialog):
    def __init__(self, entry=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑台词")
        self.resize(540, 280)
        self.entry = copy.deepcopy(entry or dict(id=uuid.uuid4().hex, category="点击回应", text="", enabled=True))
        form = QFormLayout(self)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(CATEGORIES)
        self.category.setCurrentText(self.entry["category"])
        self.text = QPlainTextEdit(self.entry["text"])
        self.enabled = QCheckBox("参与台词库语音生成")
        self.enabled.setChecked(self.entry["enabled"])
        form.addRow("分类", self.category)
        form.addRow("台词", self.text)
        form.addRow("", self.enabled)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        form.addRow(controls)

    def accept(self):
        try:
            self.entry.update(category=self.category.currentText().strip(), text=self.text.toPlainText().strip(), enabled=self.enabled.isChecked())
            self.entry = normalize_dialogues([self.entry])[0]
        except ValueError as exc:
            QMessageBox.warning(self, "台词无效", str(exc))
            return
        super().accept()


class LibraryMixin:
    def build_library_tab(self):
        from .ui import button, hint, row
        self.library_records = []
        self.library_busy = False
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(hint("只读发现工坊、本地创作和附加目录中的 project.json；勾选后可批量创建或修改绑定。双击已绑定壁纸进入其配置。"))
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("搜索标题、工坊 ID 或路径…")
        self.library_search.textChanged.connect(self.filter_library)
        layout.addWidget(row(self.library_search, button("扫描壁纸库", self.scan_library, True)))
        self.library_table = QTableWidget(0, 7)
        self.library_table.setHorizontalHeaderLabels(["勾选", "壁纸", "类型", "工坊 ID", "绑定状态", "语音目录", "BGM 目录"])
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.library_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.library_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in [4, 5, 6]:
            self.library_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.library_table.setColumnWidth(column, 135)
        self.library_table.cellDoubleClicked.connect(lambda r, c: self.open_library_profile())
        layout.addWidget(self.library_table, 1)
        layout.addWidget(row(button("全选可见", lambda: self.check_library(True)), button("取消可见勾选", lambda: self.check_library(False)),
                             button("批量创建 / 修改绑定", self.batch_bind_library, True), button("打开选中配置", self.open_library_profile)))
        layout.addWidget(button("批量删除勾选壁纸的绑定（保留全部文件）", self.delete_library_bindings))
        self.library_status = hint("尚未扫描")
        layout.addWidget(self.library_status)
        self.extra_library_roots = QPlainTextEdit("\n".join(self.store.config.get("library_roots", [])))
        self.extra_library_roots.setMaximumHeight(65)
        self.extra_library_roots.setPlaceholderText("附加壁纸库目录，每行一个；工坊和 WE 本地创作目录会自动扫描")
        layout.addWidget(self.extra_library_roots)
        layout.addWidget(row(button("添加扫描目录…", self.add_library_root), button("保存目录并扫描", self.save_library_roots)))
        self.library_tab_index = self.tabs.addTab(page, "壁纸库")

    def add_library_root(self):
        value = QFileDialog.getExistingDirectory(self, "选择附加壁纸库目录")
        if value:
            values = [line.strip() for line in self.extra_library_roots.toPlainText().splitlines() if line.strip()]
            if value not in values:
                values.append(value)
            self.extra_library_roots.setPlainText("\n".join(values))

    def save_library_roots(self):
        values = [str(Path(line.strip()).expanduser().resolve()) for line in self.extra_library_roots.toPlainText().splitlines() if line.strip()]
        if any(not Path(value).is_dir() for value in values):
            self.report_error("有扫描目录不存在，请修改后保存。")
            return
        try:
            self.store.config["library_roots"] = list(dict.fromkeys(values))
            self.store.save()
            self.scan_library()
            if hasattr(self, "autosave"):
                self.autosave.remember("roots")
            return True
        except Exception as exc:
            self.report_error(str(exc))
            return False

    def scan_library(self):
        if self.library_busy:
            return
        self.library_busy = True
        self.library_status.setText("正在后台扫描…")
        scanner = self.registry.libraries[self.store.config.get("library_backend", "wallpaper_engine")][1]
        config = copy.deepcopy(self.store.config)
        self.submit(lambda: scanner(config), self.library_scanned, self.library_scan_error)

    def library_scanned(self, result):
        self.library_busy = False
        self.library_records = result["records"]
        self.render_library()
        warnings = result.get("warnings", [])
        self.library_status.setText(f"发现 {len(self.library_records)} 张壁纸；{len(warnings)} 项目录或项目提示。勾选不会修改壁纸文件。")
        for warning in warnings[:15]:
            self.log("壁纸库：" + warning)

    def library_scan_error(self, error):
        self.library_busy = False
        self.library_status.setText("扫描失败：" + str(error))
        self.log(self.library_status.text())

    def render_library(self):
        checked = {self.library_table.item(i, 0).data(Qt.ItemDataRole.UserRole) for i in range(self.library_table.rowCount())
                   if self.library_table.item(i, 0).checkState() == Qt.CheckState.Checked}
        self.library_table.setRowCount(len(self.library_records))
        for i, record in enumerate(self.library_records):
            key = identity(record["path"])
            p = self.store.bound_profile(record["path"])
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setData(Qt.ItemDataRole.UserRole, key)
            check.setCheckState(Qt.CheckState.Checked if key in checked else Qt.CheckState.Unchecked)
            self.library_table.setItem(i, 0, check)
            values = [record["title"], record["type"], record["workshop_id"], p["name"] if p else "未绑定", p["voice_dir"] if p else "", p["bgm_dir"] if p else ""]
            for j, value in enumerate(values, 1):
                item = QTableWidgetItem(value)
                item.setToolTip(value + ("\n" + record["path"] if j == 1 else ""))
                self.library_table.setItem(i, j, item)
        self.filter_library()

    def filter_library(self):
        query = self.library_search.text().strip().casefold()
        for i, record in enumerate(self.library_records):
            self.library_table.setRowHidden(i, query not in " ".join(str(v) for v in record.values()).casefold())

    def check_library(self, enabled):
        for i in range(self.library_table.rowCount()):
            if not self.library_table.isRowHidden(i):
                self.library_table.item(i, 0).setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)

    def checked_wallpapers(self):
        return [record for i, record in enumerate(self.library_records)
                if self.library_table.item(i, 0).checkState() == Qt.CheckState.Checked]

    def batch_bind_library(self):
        records = self.checked_wallpapers()
        if not records:
            QMessageBox.information(self, "请勾选壁纸", "先在列表左侧勾选需要绑定的壁纸。")
            return
        selected = self.store.profile(self.editing_id)
        dialog = BatchBindDialog(self.store.config["profiles"], len(records), selected, self)
        if dialog.exec():
            self.apply_library_bindings(records, dialog.options())

    def apply_library_bindings(self, records, options):
        try:
            if self.editing_id and self.draft_profile() != self.store.profile(self.editing_id):
                if not self.save_profile():
                    return
            result = apply_bindings(self.store, records, **options)
            self.refresh_profiles(self.editing_id)
            self.render_library()
            self.activate_profile(force=True)
            self.library_status.setText(f"已新增 {result['created']} 个绑定，更新 {result['updated']} 个，保留 {result['skipped']} 个已有绑定。")
            self.log(self.library_status.text())
            return result
        except Exception as exc:
            self.report_error(str(exc))

    def open_library_profile(self):
        index = self.library_table.currentRow()
        if index < 0:
            return
        profile = self.store.bound_profile(self.library_records[index]["path"])
        if not profile:
            QMessageBox.information(self, "尚未绑定", "请先勾选此壁纸并使用批量绑定。")
            return
        self.refresh_profiles(profile["id"])
        self.tabs.setCurrentIndex(0)

    def delete_library_bindings(self):
        ids = [p["id"] for record in self.checked_wallpapers() if (p := self.store.bound_profile(record["path"]))]
        if not ids:
            QMessageBox.information(self, "没有已绑定项", "请勾选至少一个已经绑定的壁纸。")
            return
        self.delete_profile_ids(ids)


class DialogueMixin:
    def build_dialogue_tab(self):
        from .ui import button, hint, row
        self.edit_dialogues = []
        self.shared_dialogue_snapshot = None
        self.shared_dialogue_error = False
        page = QWidget()
        layout = QVBoxLayout(page)
        self.dialogue_context = hint("未选择壁纸时编辑共享台词；选择壁纸后编辑其台词库。保存文字不会调用语音服务。")
        layout.addWidget(self.dialogue_context)
        self.dialogue_table = QTableWidget(0, 3)
        self.dialogue_table.setHorizontalHeaderLabels(["生成", "分类", "台词（双击可编辑）"])
        self.dialogue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dialogue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dialogue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.dialogue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.dialogue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dialogue_table.cellDoubleClicked.connect(lambda r, c: self.edit_dialogue())
        layout.addWidget(self.dialogue_table, 1)
        self.dialogue_category_choice = QComboBox()
        layout.addWidget(row(button("全选台词", lambda: self.select_dialogues("all")),
                             button("全不选台词", lambda: self.select_dialogues("none")),
                             self.dialogue_category_choice, button("选择此分类", lambda: self.select_dialogues("category"))))
        layout.addWidget(row(button("＋ 新台词", self.add_dialogue), button("编辑", self.edit_dialogue), button("删除", self.delete_dialogues),
                             button("补充默认台词", self.add_starter_dialogues), button("保存台词库", self.save_dialogue_library, True)))
        self.skip_existing_dialogue_audio = QCheckBox("生成时跳过已存在的同名音频")
        self.skip_existing_dialogue_audio.setChecked(True)
        layout.addWidget(self.skip_existing_dialogue_audio)
        layout.addWidget(row(button("将勾选台词送到生成页", self.send_dialogues_to_tts),
                             button("按分类生成勾选台词", self.generate_dialogue_library, True)))
        layout.addWidget(row(button("应用分类触发规则", self.install_dialogue_rules),
                             button("导入台词 JSON / TXT", self.import_dialogues), button("导出台词 JSON", self.export_dialogues)))
        layout.addWidget(hint("按分类生成会保存到语音目录/早晨、语音目录/点击回应等子目录；生成前可在“生成语音”页选择服务。\n"
                              "应用分类规则会替换当前编辑中的规则，保存后生效。原始下载音频无需台词库，也能直接播放。"))
        self.dialogue_tab_index = self.tabs.addTab(page, "台词库")

    def load_shared_dialogue_library(self):
        from .assets import load_dialogues, shared_root
        self.shared_dialogue_error = False
        try:
            self.edit_dialogues = load_dialogues(dict(dialogue_file=str(shared_root(self.store) / "dialogues.json")))
        except (ValueError, OSError) as exc:
            self.shared_dialogue_error = True
            self.edit_dialogues = []
            self.report_error("共享台词文件读取失败，原文件未改动：" + str(exc))
        self.shared_dialogue_snapshot = copy.deepcopy(self.edit_dialogues)
        self.render_dialogues()

    def save_dialogue_library(self):
        if self.editing_id:
            return self.save_profile()
        from .assets import shared_root, write_dialogues
        try:
            if self.shared_dialogue_error:
                raise ValueError("原共享台词文件读取失败，请先修复它或在音频库选择另一共享目录；未覆盖原文件。")
            entries = normalize_dialogues(self.collect_dialogues())
            write_dialogues(shared_root(self.store) / "dialogues.json", entries, self.store.protected())
            self.shared_dialogue_snapshot = copy.deepcopy(entries)
            self.dialogue_context.setText(f"已保存共享台词库 · {len(entries)} 条；新共享绑定将使用这些台词。")
            self.log(self.dialogue_context.text())
            return True
        except Exception as exc:
            self.report_error(str(exc))
            return False

    def collect_dialogues(self):
        return copy.deepcopy(self.edit_dialogues)

    def select_dialogues(self, mode):
        category = self.dialogue_category_choice.currentText()
        for i, entry in enumerate(self.edit_dialogues):
            selected = mode == "all" or mode == "category" and entry["category"] == category
            self.dialogue_table.item(i, 0).setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)
        self.log(f"本次生成已选择 {len(self.selected_dialogues())} 条台词；勾选不改变台词库内容。")

    def render_dialogues(self):
        scope_id = self.editing_id or "shared"
        selected = {self.dialogue_table.item(i, 0).data(Qt.ItemDataRole.UserRole)
                    for i in range(self.dialogue_table.rowCount()) if self.dialogue_table.item(i, 0) and self.dialogue_table.item(i, 0).checkState() == Qt.CheckState.Checked}
        if getattr(self, "dialogue_selection_scope", None) != scope_id:
            selected = set()
        self.dialogue_selection_scope = scope_id
        scope = "壁纸台词库：" + self.profile_name.text() if self.editing_id else "共享台词库（无需先绑定壁纸）"
        self.dialogue_context.setText(f"{scope} · {len(self.edit_dialogues)} 条；切换页面自动保存，也可手动保存。生成勾选只对本次操作有效。")
        self.dialogue_table.setRowCount(len(self.edit_dialogues))
        for i, entry in enumerate(self.edit_dialogues):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setData(Qt.ItemDataRole.UserRole, entry["id"])
            check.setCheckState(Qt.CheckState.Checked if entry["id"] in selected else Qt.CheckState.Unchecked)
            self.dialogue_table.setItem(i, 0, check)
            for j, key in enumerate(["category", "text"], 1):
                item = QTableWidgetItem(entry[key])
                item.setToolTip(entry[key])
                self.dialogue_table.setItem(i, j, item)
        previous = self.dialogue_category_choice.currentText()
        self.dialogue_category_choice.clear()
        self.dialogue_category_choice.addItems(list(dict.fromkeys(e["category"] for e in self.edit_dialogues)))
        self.dialogue_category_choice.setCurrentText(previous)

    def add_dialogue(self):
        self.collect_dialogues()
        dialog = DialogueDialog(parent=self)
        if dialog.exec():
            self.edit_dialogues.append(dialog.entry)
            self.render_dialogues()

    def edit_dialogue(self):
        i = self.dialogue_table.currentRow()
        if i >= 0:
            self.collect_dialogues()
            dialog = DialogueDialog(self.edit_dialogues[i], self)
            if dialog.exec():
                self.edit_dialogues[i] = dialog.entry
                self.render_dialogues()

    def delete_dialogues(self):
        self.collect_dialogues()
        selected = {index.row() for index in self.dialogue_table.selectionModel().selectedRows()}
        self.edit_dialogues = [entry for i, entry in enumerate(self.edit_dialogues) if i not in selected]
        self.render_dialogues()

    def add_starter_dialogues(self):
        self.collect_dialogues()
        before = len(self.edit_dialogues)
        existing = {(entry["category"], entry["text"]) for entry in self.edit_dialogues}
        for entry in starter_dialogues():
            if (entry["category"], entry["text"]) not in existing:
                entry["id"] = uuid.uuid4().hex
                self.edit_dialogues.append(entry)
        self.render_dialogues()
        added = len(self.edit_dialogues) - before
        self.dialogue_context.setText(f"已补充 {added} 条默认台词，请保存台词库。" if added else "默认台词已齐全，无需重复添加。")

    def selected_dialogues(self):
        return [{**entry, "enabled": True} for i, entry in enumerate(normalize_dialogues(self.collect_dialogues()))
                if self.dialogue_table.item(i, 0).checkState() == Qt.CheckState.Checked]

    def send_dialogues_to_tts(self):
        lines = self.selected_dialogues()
        self.lines.setPlainText("\n".join(entry["text"] for entry in lines))
        if self.editing_id:
            self.use_voice_dir()
        else:
            from .assets import shared_root
            self.tts_output.setText(str(shared_root(self.store) / "voice"))
        self.tabs.setCurrentIndex(2)

    def install_dialogue_rules(self):
        if not self.editing_id:
            self.report_error("应用触发规则前，请先绑定壁纸或新建一个壁纸配置；共享台词本身不启动播放。")
            return
        if QMessageBox.question(self, "应用分类触发规则", "将当前编辑的规则替换为 F8/中键回应、壁纸切入问候、早晨/白天/夜间随机语音？保存配置后生效。") == QMessageBox.StandardButton.Yes:
            self.edit_rules = dialogue_rules()
            self.render_rules()
            self.log("已填入分类规则，点击保存配置后生效。")

    def import_dialogues(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入台词", "", "台词文件 (*.json *.txt)")
        if not path:
            return
        try:
            value = Path(path).read_text(encoding="utf-8-sig")
            entries = json.loads(value) if Path(path).suffix.casefold() == ".json" else [dict(text=line, category="点击回应", enabled=True) for line in value.splitlines() if line.strip()]
            entries = normalize_dialogues(entries)
            self.collect_dialogues()
            existing = {(e["category"], e["text"]) for e in self.edit_dialogues}
            for entry in entries:
                if (entry["category"], entry["text"]) not in existing:
                    entry["id"] = uuid.uuid4().hex
                    self.edit_dialogues.append(entry)
                    existing.add((entry["category"], entry["text"]))
            self.render_dialogues()
            self.log("已导入台词到编辑区，保存后生效。")
        except Exception as exc:
            self.report_error(str(exc))

    def export_dialogues(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出台词", "dialogues.json", "JSON (*.json)")
        if path:
            try:
                writable_path(path, self.store.protected()).write_text(json.dumps(normalize_dialogues(self.collect_dialogues()), ensure_ascii=False, indent=2), encoding="utf-8")
                self.log("台词已导出：" + path)
            except Exception as exc:
                self.report_error(str(exc))

    def generate_dialogue_library(self):
        from .services import generate_dialogue_entries
        if self.tts_busy or self.api_busy:
            self.api_message("已有语音或接口任务正在进行，请等待完成。")
            return
        try:
            entries = self.selected_dialogues()
            from .assets import shared_root
            folder = self.voice_dir.text().strip() if self.editing_id else str(shared_root(self.store) / "voice")
            if not entries or not folder:
                raise ValueError("请勾选台词，并先在声音与互动页选择语音目录")
            if not self.save_dialogue_library():
                return
            settings = self.tts_settings()
            if not self.save_tts():
                return
            provider = self.registry.speech[self.provider_choice.currentData()]
            folder = str(writable_path(folder, self.store.protected()))
            skip = self.skip_existing_dialogue_audio.isChecked()
            protected = self.store.protected()
        except Exception as exc:
            self.report_error(str(exc))
            return
        self.tts_busy = True
        self.update_api_controls()
        self.begin_generation(len(entries))
        self.generation_cancel.clear()
        self.generate_button.setEnabled(False)
        self.tts_status.setText(f"正在按分类生成 {len(entries)} 条台词…")
        self.tabs.setCurrentIndex(2)
        self.submit(lambda: generate_dialogue_entries(settings, entries, folder, protected, self.progress.emit, provider, skip, self.generation_cancel, status=self.generation_state.emit), self.dialogue_generated, self.generation_error)

    def dialogue_generated(self, result):
        self.generated(result["paths"])
        self.tts_status.setText(f"分类生成完成：新增 {len(result['paths'])} 条，跳过 {result['skipped']} 条已有音频。")
