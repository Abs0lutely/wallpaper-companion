"""Library and dialogue widgets, kept separate from the host window."""
from .i18n import tr
import copy
import json
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from .file_dialogs import FileDialogs as QFileDialog

from .core import identity, writable_path
from .dialogues import CATEGORIES, dialogue_rules, normalize_dialogues, starter_dialogues
from .library import apply_bindings


class BatchBindDialog(QDialog):
    def __init__(self, profiles, count, selected=None, parent=None):
        from .ui import hint, path_field, row
        super().__init__(parent)
        self.setWindowTitle(tr('ui.a2f448ec169a', '批量绑定壁纸'))
        self.resize(650, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(hint(tr('ui.f26d80cf4f75', '已勾选 {value0} 张壁纸。已有绑定默认跳过；只有勾选更新才替换其音频目录，现有名称和规则仍保留。', value0=count)))
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem(tr('ui.5ea5b4f96781', '共用语音 / BGM 目录'), "shared")
        self.mode.addItem(tr('ui.8126bb209a73', '共用完整资源目录（含台词库）'), "shared_root")
        self.mode.addItem(tr('ui.fba225e66f2e', '为每张壁纸建立独立目录'), "separate")
        self.asset = QLineEdit(selected.get("asset_dir", "") if selected else "")
        if parent is not None and hasattr(parent, "store"):
            from .assets import shared_root
            self.asset.setText(str(shared_root(parent.store)))
        self.voice = QLineEdit(selected.get("voice_dir", "") if selected else "")
        self.bgm = QLineEdit(selected.get("bgm_dir", "") if selected else "")
        self.template = QComboBox()
        self.template.addItem(tr('ui.ac7188b02a57', '默认设置和规则'), "")
        for profile in profiles:
            self.template.addItem(profile["name"], profile["id"])
        if selected:
            self.template.setCurrentIndex(max(0, self.template.findData(selected["id"])))
        self.update_existing = QCheckBox(tr('ui.20e91df4455c', '同时更新已有配置的资源目录绑定'))
        self.update_existing.setChecked(False)
        form.addRow(tr('ui.86f8b75c706f', '目录方式'), self.mode)
        form.addRow(tr('ui.7692e5a3426f', '共享资源根目录'), path_field(self.asset))
        form.addRow(tr('ui.35740c0c431d', '语音目录'), path_field(self.voice))
        form.addRow(tr('ui.f87fb30e5e1e', 'BGM 目录（可空）'), path_field(self.bgm))
        form.addRow(tr('ui.f3ce8f920150', '新配置模板'), self.template)
        form.addRow(tr('ui.3780d09b269f', '已有绑定'), self.update_existing)
        layout.addLayout(form)
        layout.addWidget(hint(tr('ui.33b9cf3b50b2', '共享模式无需为每张壁纸重复生成语音。独立模式的目录只建立在声伴自身数据目录中，不改动壁纸文件。模板只用于新绑定。')))
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
            QMessageBox.warning(self, tr('ui.9e7393498b9f', '请选择根目录'), tr('ui.175304832b5b', '共享完整资源需要选择根目录。'))
            return
        if self.mode.currentData() == "shared":
            if not self.voice.text().strip() or not Path(self.voice.text().strip()).is_dir():
                QMessageBox.warning(self, tr('ui.810b25086189', '请检查目录'), tr('ui.958f2200d7de', '共享模式需要选择已存在的语音目录。'))
                return
            if self.bgm.text().strip() and not Path(self.bgm.text().strip()).is_dir():
                QMessageBox.warning(self, tr('ui.810b25086189', '请检查目录'), tr('ui.62ceb715362a', 'BGM 目录不存在。'))
                return
        super().accept()


class DialogueDialog(QDialog):
    def __init__(self, entry=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('ui.c5533f4fa0a3', '编辑台词'))
        self.resize(540, 280)
        self.entry = copy.deepcopy(entry or dict(id=uuid.uuid4().hex, category="点击回应", text="", enabled=True))
        form = QFormLayout(self)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(CATEGORIES)
        self.category.setCurrentText(self.entry["category"])
        self.text = QPlainTextEdit(self.entry["text"])
        form.addRow(tr('ui.515559957fd3', '分类'), self.category)
        form.addRow(tr('ui.e7447595378a', '台词'), self.text)
        form.addRow("", QLabel(tr('ui.252c292c84d0', '保存后在台词库列表勾选本次需要生成的条目。')))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        form.addRow(controls)

    def accept(self):
        try:
            self.entry.update(category=self.category.currentText().strip(), text=self.text.toPlainText().strip())
            self.entry = normalize_dialogues([self.entry])[0]
        except ValueError as exc:
            QMessageBox.warning(self, tr('ui.f59fdb0472d7', '台词无效'), str(exc))
            return
        super().accept()


class LibraryMixin:
    def build_library_tab(self):
        from .ui import button, hint, row
        self.library_records = []
        self.library_busy = False
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(hint(tr('ui.095636d29a04', '只读发现工坊、本地创作和附加目录中的 project.json；勾选后可批量创建或修改绑定。双击已绑定壁纸进入其配置。')))
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText(tr('ui.bc4442ffd430', '搜索标题、工坊 ID 或路径…'))
        self.library_search.textChanged.connect(self.filter_library)
        layout.addWidget(row(self.library_search, button(tr('ui.22d62264011f', '扫描壁纸库'), self.scan_library, True)))
        self.library_table = QTableWidget(0, 7)
        self.library_table.setHorizontalHeaderLabels([tr('ui.c6cdcd00b6a5', '勾选'), tr('ui.bbaa9f06378b', '壁纸'), tr('ui.ba40014ff496', '类型'), tr('ui.03abec8bf212', '工坊 ID'), tr('ui.6781efe68e80', '绑定状态'), tr('ui.35740c0c431d', '语音目录'), tr('ui.d1f147aa4d10', 'BGM 目录')])
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.library_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.library_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in [4, 5, 6]:
            self.library_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.library_table.setColumnWidth(column, 135)
        self.library_table.cellDoubleClicked.connect(lambda r, c: self.open_library_profile())
        layout.addWidget(self.library_table, 1)
        layout.addWidget(row(button(tr('ui.3d5510e6fa98', '全选可见'), lambda: self.check_library(True)), button(tr('ui.ebe780dbf8bb', '取消可见勾选'), lambda: self.check_library(False)),
                             button(tr('ui.7582301f85cf', '批量创建 / 修改绑定'), self.batch_bind_library, True), button(tr('ui.927861e7b32f', '打开选中配置'), self.open_library_profile)))
        layout.addWidget(button(tr('ui.8ce985a33630', '批量删除勾选壁纸的绑定（保留全部文件）'), self.delete_library_bindings))
        self.library_status = hint(tr('ui.5f6b5f6c5c51', '尚未扫描'))
        layout.addWidget(self.library_status)
        self.extra_library_roots = QPlainTextEdit("\n".join(self.store.config.get("library_roots", [])))
        self.extra_library_roots.setMaximumHeight(65)
        self.extra_library_roots.setPlaceholderText(tr('ui.4293c9c73b42', '附加壁纸库目录，每行一个；工坊和 WE 本地创作目录会自动扫描'))
        layout.addWidget(self.extra_library_roots)
        layout.addWidget(row(button(tr('ui.6784c4ec422f', '添加扫描目录…'), self.add_library_root), button(tr('ui.1a4d26554d01', '保存目录并扫描'), self.save_library_roots)))
        self.library_tab_index = self.tabs.addTab(page, tr('ui.99ffa5dff575', '壁纸库'))

    def add_library_root(self):
        value = QFileDialog.getExistingDirectory(self, tr('ui.7ed133adc137', '选择附加壁纸库目录'))
        if value:
            values = [line.strip() for line in self.extra_library_roots.toPlainText().splitlines() if line.strip()]
            if value not in values:
                values.append(value)
            self.extra_library_roots.setPlainText("\n".join(values))

    def save_library_roots(self):
        values = [str(Path(line.strip()).expanduser().resolve()) for line in self.extra_library_roots.toPlainText().splitlines() if line.strip()]
        if any(not Path(value).is_dir() for value in values):
            self.report_error(tr('ui.4ae2c4d06aee', '有扫描目录不存在，请修改后保存。'))
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
        if self.is_standalone():return
        if self.library_busy:
            return
        self.library_busy = True
        self.library_status.setText(tr('ui.fd46291980eb', '正在后台扫描…'))
        scanner = self.registry.libraries[self.store.config.get("library_backend", "wallpaper_engine")][1]
        config = copy.deepcopy(self.store.config)
        self.submit(lambda: scanner(config), self.library_scanned, self.library_scan_error)

    def library_scanned(self, result):
        self.library_busy = False
        self.library_records = result["records"]
        self.render_library()
        warnings = result.get("warnings", [])
        self.library_status.setText(tr('ui.3f7def6201d9', '发现 {value0} 张壁纸；{value1} 项目录或项目提示。勾选不会修改壁纸文件。', value0=len(self.library_records), value1=len(warnings)))
        for warning in warnings[:15]:
            self.log(tr('ui.ab49253ac4e0', '壁纸库：') + warning)

    def library_scan_error(self, error):
        self.library_busy = False
        self.library_status.setText(tr('ui.bdf9f50cd8db', '扫描失败：') + str(error))
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
            values = [record["title"], record["type"], record["workshop_id"], p["name"] if p else tr('ui.e026c6693dc5', '未绑定'), p["voice_dir"] if p else "", p["bgm_dir"] if p else ""]
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
            QMessageBox.information(self, tr('ui.0e43a22047a3', '请勾选壁纸'), tr('ui.a3ca6656687f', '先在列表左侧勾选需要绑定的壁纸。'))
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
            self.library_status.setText(tr('ui.06d47d855fb7', '已新增 {value0} 个绑定，更新 {value1} 个，保留 {value2} 个已有绑定。', value0=result['created'], value1=result['updated'], value2=result['skipped']))
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
            QMessageBox.information(self, tr('ui.1332a0b73a7b', '尚未绑定'), tr('ui.1c726ee184f8', '请先勾选此壁纸并使用批量绑定。'))
            return
        self.refresh_profiles(profile["id"])
        self.tabs.setCurrentIndex(0)

    def delete_library_bindings(self):
        ids = [p["id"] for record in self.checked_wallpapers() if (p := self.store.bound_profile(record["path"]))]
        if not ids:
            QMessageBox.information(self, tr('ui.60a0c2765e32', '没有已绑定项'), tr('ui.41ae6c9b9453', '请勾选至少一个已经绑定的壁纸。'))
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
        self.dialogue_context = hint(tr('ui.b0ca891589cd', '未选择壁纸时编辑共享台词；选择壁纸后编辑其台词库。保存文字不会调用语音服务。'))
        layout.addWidget(self.dialogue_context)
        from .dialogue_table import DialogueTable
        self.dialogue_table = DialogueTable(0, 3)
        self.dialogue_table.setHorizontalHeaderLabels([tr('ui.1ad1463fe16f', '生成'), tr('ui.515559957fd3', '分类'), tr('ui.25f4d50c463f', '台词（双击可编辑）')])
        self.dialogue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dialogue_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.dialogue_table.itemSelectionChanged.connect(self.sync_dialogue_checks)
        self.dialogue_table.itemChanged.connect(self.sync_dialogue_selection)
        self.dialogue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dialogue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.dialogue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.dialogue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dialogue_table.cellDoubleClicked.connect(lambda r, c: self.edit_dialogue() if c != 0 else None)
        layout.addWidget(self.dialogue_table, 1)
        self.dialogue_category_choice = QComboBox()
        layout.addWidget(row(button(tr('ui.aef57f37c988', '全选台词'), lambda: self.select_dialogues("all")),
                             button(tr('ui.c6fe1d00f87e', '全不选台词'), lambda: self.select_dialogues("none")),
                             self.dialogue_category_choice, button(tr('ui.59242f23fd23', '选择此分类'), lambda: self.select_dialogues("category"))))
        layout.addWidget(row(button(tr('ui.3eb41b973877', '＋ 新台词'), self.add_dialogue), button(tr('ui.051836569928', '编辑'), self.edit_dialogue), button(tr('ui.2f9daa828907', '删除'), self.delete_dialogues),
                             button(tr('ui.ac45d38300d9', '补充默认台词'), self.add_starter_dialogues), button(tr('ui.30898e1ec4d0', '保存台词库'), self.save_dialogue_library, True)))
        self.skip_existing_dialogue_audio = QCheckBox(tr('ui.3f28002fa210', '生成时跳过已存在的同名音频'))
        self.skip_existing_dialogue_audio.setChecked(True)
        self.skip_existing_dialogue_audio.toggled.connect(self.skip_existing_tts_audio.setChecked)
        self.skip_existing_tts_audio.toggled.connect(self.skip_existing_dialogue_audio.setChecked)
        layout.addWidget(self.skip_existing_dialogue_audio)
        layout.addWidget(row(button(tr('ui.3b8118a7c3de', '将勾选台词送到生成页'), self.send_dialogues_to_tts, True)))
        self.rules_locale=QComboBox()
        for label,code in [("中文","zh-CN"),("日本語","ja-JP"),("English","en-US")]:self.rules_locale.addItem(label,code)
        layout.addWidget(self.rules_locale)
        layout.addWidget(row(button(tr('ui.7d9ab8f2b401', '应用分类触发规则'), self.install_dialogue_rules),
                             button(tr('ui.5dad01da2d96', '导入台词 JSON / TXT'), self.import_dialogues), button(tr('ui.01d53f80e251', '导出台词 JSON'), self.export_dialogues)))
        layout.addWidget(row(button(tr('ui.6e2442e35392', '导入默认操作台词'), self.add_operation_dialogues), button(tr("voices.migrate", "更新旧译文分类…"), self.migrate_dialogue_categories)))
        layout.addWidget(hint(tr("voices.transfer_help", "勾选后送到生成页，将按原分类保存音频；修改转入的文本后改为普通逐行生成。分类规则会替换当前规则。")))
        self.dialogue_tab_index = self.tabs.addTab(page, tr('ui.40949e0e28ee', '台词库'))

    def load_shared_dialogue_library(self):
        from .assets import load_dialogues, shared_root
        self.shared_dialogue_error = False
        try:
            self.edit_dialogues = load_dialogues(dict(dialogue_file=str(shared_root(self.store) / "dialogues.json")))
        except (ValueError, OSError) as exc:
            self.shared_dialogue_error = True
            self.edit_dialogues = []
            self.report_error(tr('ui.5ccfed0a5508', '共享台词文件读取失败，原文件未改动：') + str(exc))
        self.shared_dialogue_snapshot = copy.deepcopy(self.edit_dialogues)
        self.render_dialogues()

    def save_dialogue_library(self):
        if self.editing_id:
            return self.save_profile()
        from .assets import shared_root, write_dialogues
        try:
            if self.shared_dialogue_error:
                raise ValueError(tr('ui.2dd87d3ead4c', '原共享台词文件读取失败，请先修复它或在音频库选择另一共享目录；未覆盖原文件。'))
            entries = normalize_dialogues(self.collect_dialogues())
            write_dialogues(shared_root(self.store) / "dialogues.json", entries, self.store.protected())
            self.shared_dialogue_snapshot = copy.deepcopy(entries)
            self.dialogue_context.setText(tr('ui.d1133429e489', '已保存共享台词库 · {value0} 条；新共享绑定将使用这些台词。', value0=len(entries)))
            self.log(self.dialogue_context.text())
            return True
        except Exception as exc:
            self.report_error(str(exc))
            return False

    def collect_dialogues(self):
        return copy.deepcopy(self.edit_dialogues)

    def select_dialogues(self, mode):
        category = self.dialogue_category_choice.currentText()
        self.dialogue_table.blockSignals(True)
        for i, entry in enumerate(self.edit_dialogues):
            selected = mode == "all" or mode == "category" and entry["category"] == category
            self.dialogue_table.item(i, 0).setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)
        self.dialogue_table.blockSignals(False)
        self.sync_dialogue_selection()
        self.log(tr('ui.85af42b751b4', '本次生成已选择 {value0} 条台词；勾选不改变台词库内容。', value0=len(self.selected_dialogues())))

    def sync_dialogue_checks(self):
        selected = {index.row() for index in self.dialogue_table.selectionModel().selectedRows()}
        self.dialogue_table.blockSignals(True)
        for i in range(self.dialogue_table.rowCount()):
            item = self.dialogue_table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked if i in selected else Qt.CheckState.Unchecked)
        self.dialogue_table.blockSignals(False)

    def sync_dialogue_selection(self, item=None):
        if item is not None and item.column() != 0:
            return
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        selection = QItemSelection()
        for i in range(self.dialogue_table.rowCount()):
            check = self.dialogue_table.item(i, 0)
            if check and check.checkState() == Qt.CheckState.Checked:
                selection.select(self.dialogue_table.model().index(i, 0), self.dialogue_table.model().index(i, 2))
        self.dialogue_table.blockSignals(True)
        self.dialogue_table.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.dialogue_table.blockSignals(False)

    def render_dialogues(self):
        scope_id = self.editing_id or "shared"
        selected = {self.dialogue_table.item(i, 0).data(Qt.ItemDataRole.UserRole)
                    for i in range(self.dialogue_table.rowCount()) if self.dialogue_table.item(i, 0) and self.dialogue_table.item(i, 0).checkState() == Qt.CheckState.Checked}
        if getattr(self, "dialogue_selection_scope", None) != scope_id:
            selected = set()
        self.dialogue_selection_scope = scope_id
        self.dialogue_table.blockSignals(True)
        scope = tr('ui.7356c5dad5c4', '壁纸台词库：') + self.profile_name.text() if self.editing_id else tr('ui.099bedcec68c', '共享台词库（无需先绑定壁纸）')
        self.dialogue_context.setText(tr('ui.2cc838eddfa7', '{value0} · {value1} 条；切换页面自动保存，也可手动保存。生成勾选只对本次操作有效。', value0=scope, value1=len(self.edit_dialogues)))
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
        self.dialogue_table.blockSignals(False)
        self.sync_dialogue_selection()
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
        self.dialogue_context.setText(tr('ui.9bda2f4875b5', '已补充 {value0} 条默认台词，请保存台词库。', value0=added) if added else tr('ui.efaa9e0d0c76', '默认台词已齐全，无需重复添加。'))

    def add_operation_dialogues(self):
        from .action_lines import operation_dialogues
        existing = {(entry["category"], entry["text"]) for entry in self.edit_dialogues}
        added = [entry for entry in operation_dialogues() if (entry["category"], entry["text"]) not in existing]
        self.edit_dialogues.extend(added)
        self.render_dialogues()
        self.tabs.setCurrentIndex(self.dialogue_tab_index)
        self.log(tr('ui.eafaa6af8f2a', '已补充 {value0} 条操作台词，未自动勾选。可按分类生成到共享语音目录，操作语音会自动发现它们。', value0=len(added)))

    def migrate_dialogue_categories(self):
        from .voice_locales import migrate_categories
        entries,changes=migrate_categories(self.collect_dialogues())
        if not changes:
            self.log(tr("voices.no_migration", "没有需要更新的旧译文分类。"));return
        details="\n".join(a+" → "+b+" : "+text for a,b,text in changes)
        dialog=QMessageBox(QMessageBox.Icon.Question,tr("voices.migrate", "更新旧译文分类…"),tr("voices.migration_preview", "识别到 {count} 条默认译文。只更新分类，不移动音频；自定义条目保留。确认后仍需保存。",count=len(changes)),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,self)
        dialog.setDetailedText(details);dialog.setDefaultButton(QMessageBox.StandardButton.No)
        if dialog.exec()==QMessageBox.StandardButton.Yes:
            self.edit_dialogues=entries;self.render_dialogues()

    def selected_dialogues(self):
        return [{**entry, "enabled": True} for i, entry in enumerate(normalize_dialogues(self.collect_dialogues()))
                if self.dialogue_table.item(i, 0).checkState() == Qt.CheckState.Checked]

    def transferred_text_changed(self):
        if self.transferred_dialogues and self.lines.toPlainText() != self.transferred_lines:
            self.tts_status.setText(tr("voices.transfer_edited", "文本已修改：将按普通逐行模式保存到输出目录，不再使用原分类。"))

    def send_dialogues_to_tts(self):
        lines = self.selected_dialogues()
        if not lines:
            self.log(tr('ui.903072001de8', '请先勾选需要生成的台词，可全选、全不选或按分类选择。'))
            return
        self.lines.setPlainText("\n".join(entry["text"] for entry in lines))
        self.transferred_dialogues = copy.deepcopy(lines)
        self.transferred_lines = self.lines.toPlainText()
        if self.editing_id:
            self.use_voice_dir()
        else:
            from .assets import shared_root
            self.tts_output.setText(str(shared_root(self.store) / "voice"))
        self.tabs.setCurrentIndex(2)
        self.tts_status.setText(tr('ui.d93c12883bc9', '已接收 {value0} 条台词，保留分类及跳过同名设置。生成前会检查重复；修改文本后按普通逐行模式生成。', value0=len(lines)))

    def install_dialogue_rules(self):
        if not self.editing_id:
            self.report_error(tr('ui.1cf3f8036615', '应用触发规则前，请先绑定壁纸或新建一个壁纸配置；共享台词本身不启动播放。'))
            return
        if QMessageBox.question(self, tr('ui.7d9ab8f2b401', '应用分类触发规则'), tr('ui.7f73e3204a4a', '将当前编辑的规则替换为 F8/中键回应、壁纸切入问候、早晨/白天/夜间随机语音？保存配置后生效。')) == QMessageBox.StandardButton.Yes:
            self.edit_rules = dialogue_rules()
            from .voice_locales import category_for
            for rule in self.edit_rules:rule["source"]=category_for(rule["source"],self.rules_locale.currentData())
            self.render_rules()
            self.log(tr('ui.78d42d11f62d', '已填入分类规则，点击保存配置后生效。'))

    def import_dialogues(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('ui.6f4ddd8488d2', '导入台词'), "", tr('ui.2ab7daf40064', '台词文件 (*.json *.txt)'))
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
            self.log(tr('ui.405806a1ba03', '已导入台词到编辑区，保存后生效。'))
        except Exception as exc:
            self.report_error(str(exc))

    def export_dialogues(self):
        path, _ = QFileDialog.getSaveFileName(self, tr('ui.5acfcb7d58e2', '导出台词'), "dialogues.json", "JSON (*.json)")
        if path:
            try:
                writable_path(path, self.store.protected()).write_text(json.dumps(normalize_dialogues(self.collect_dialogues()), ensure_ascii=False, indent=2), encoding="utf-8")
                self.log(tr('ui.4a0ef2687ef7', '台词已导出：') + path)
            except Exception as exc:
                self.report_error(str(exc))

    def generate_dialogue_library(self):
        from .services import generate_dialogue_entries
        if self.tts_busy or self.api_busy:
            self.api_message(tr('ui.df13d72d4ce9', '已有语音或接口任务正在进行，请等待完成。'))
            return
        try:
            entries = self.selected_dialogues()
            from .assets import shared_root
            folder = self.voice_dir.text().strip() if self.editing_id else str(shared_root(self.store) / "voice")
            if not entries or not folder:
                raise ValueError(tr('ui.99aa0dcaa4b7', '请勾选台词，并先在声音与互动页选择语音目录'))
            if not self.save_dialogue_library():
                return
            settings = self.generation_settings()
            if not self.save_tts():
                return
            provider = self.registry.speech[self.provider_choice.currentData()]
            folder = str(writable_path(folder, self.store.protected()))
            skip = self.skip_existing_dialogue_audio.isChecked()
            protected = self.store.protected()
        except Exception as exc:
            self.report_error(str(exc))
            return
        self.tabs.setCurrentIndex(2)
        self.begin_generation_review([entry["text"] for entry in entries], folder, settings, provider, skip, entries)

    def dialogue_generated(self, result):
        self.generated(result["paths"])
        self.tts_status.setText(tr('ui.7ee0cf4ea46b', '分类生成完成：新增 {value0} 条，跳过 {value1} 条已有音频。', value0=len(result['paths']), value1=result['skipped']))
