"""A unified audio library for shared folders and individual wallpaper bindings."""
from .i18n import tr
import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from .file_dialogs import FileDialogs as QFileDialog

from .record_table import RecordTable
from .assets import shared_root
from .audio_library import copy_audio, destination, inventory, locations, recycle_audio
from .core import identity, writable_path


class AudioLibraryMixin:
    def build_audio_library_tab(self):
        from .ui import button, hint, path_field, row
        self.audio_records = []
        self.audio_library_busy = False
        self.audio_refresh_pending = False
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(hint(tr('ui.08dfea087555', '统一管理共享和各壁纸目录中的音频。直接引用目录不复制文件；需要专用副本时，可复制所选音频到目标目录。删除共享文件会影响所有引用它的配置。')))
        self.audio_scope = QComboBox()
        self.audio_search = QLineEdit()
        self.audio_search.setPlaceholderText(tr('ui.fa82f51665f3', '按文件名、路径或配置名称搜索…'))
        layout.addWidget(row(QLabel(tr('ui.a9c1deca85be', '查看范围')), self.audio_scope, self.audio_search, button(tr('ui.f1832518f4fd', '刷新音频库'), self.refresh_audio_library)))
        self.audio_table = RecordTable(0, 5)
        self.audio_table.setHorizontalHeaderLabels([tr('ui.a6e48adc26d6', '文件名'), tr('ui.f61c51806feb', '用途 / 目录'), tr('ui.02fb1f090dae', '引用配置数'), tr('ui.50db7447b966', '大小'), tr('ui.778f9ad05aae', '实际路径')])
        self.audio_table.setProperty("itemHoverDetails", True)
        self.audio_table.setMouseTracking(True)
        self.audio_table.viewport().setMouseTracking(True)
        self.audio_table.horizontalHeader().setMouseTracking(True)
        for i, text in enumerate([tr('ui.470337251384', '音频的完整文件名。双击可试听。'), tr('ui.8ad88fe8737c', '该文件被哪些语音/BGM资源目录使用。'), tr('ui.e7a2ed7c6de8', '配置中引用该文件目录的壁纸数量。'), tr('ui.cb7d924fd316', '文件大小，内容悬停显示精确字节数。'), tr('ui.d14ffd2b7141', '音频文件的真实完整路径。')]):
            self.audio_table.horizontalHeaderItem(i).setToolTip(text)
        self.audio_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.audio_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.audio_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.audio_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.audio_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.audio_table.setColumnWidth(1, 220)
        self.audio_table.setColumnWidth(2, 90)
        self.audio_table.setColumnWidth(3, 85)
        self.audio_table.setColumnWidth(4, 280)
        self.audio_table.cellDoubleClicked.connect(lambda *_: self.preview_library_audio())
        layout.addWidget(self.audio_table, 1)
        layout.addWidget(row(button(tr('ui.70b25d866a2e', '全选当前列表'), lambda: self.select_library_audio(True)),
                             button(tr('ui.ab9084a640fb', '全不选'), lambda: self.select_library_audio(False)),
                             hint(tr('ui.fe15822389dd', '支持 Ctrl / Shift 多选；删除和复制对全部选中文件生效。'))))
        layout.addWidget(row(button(tr('ui.231d92a6a101', '试听所选'), self.preview_library_audio), button(tr('ui.51443cd5a288', '停止试听'), self.audio.voice.stop),
                             button(tr('ui.2b7096bf904b', '打开所选文件目录'), self.open_library_audio_folder), button(tr('ui.2f9daa828907', '删除'), self.recycle_library_audio)))
        self.audio_target = QComboBox()
        self.audio_category = QLineEdit()
        self.audio_category.setPlaceholderText(tr('ui.929a5d5cedd4', '可选分类子目录，例如：早安'))
        layout.addWidget(row(QLabel(tr('ui.048c109cacda', '导入 / 复制目标')), self.audio_target, self.audio_category))
        layout.addWidget(row(button(tr('ui.dce54f102566', '导入音频文件…'), self.import_library_audio), button(tr('ui.afd5b1b068b5', '复制所选到目标'), self.copy_library_audio)))
        layout.addWidget(row(button(tr('ui.22f235099587', '目标目录用于当前壁纸语音'), lambda: self.reference_audio_target("voice_dir")),
                             button(tr('ui.878990a3020e', '目标目录用于当前壁纸 BGM'), lambda: self.reference_audio_target("bgm_dir"))))
        self.shared_audio_root = QLineEdit(str(shared_root(self.store)))
        self.shared_audio_root.setToolTip(tr('ui.283a82daba98', '默认位于程序安装目录的 shared；修改只影响新绑定及下次显式选择共享目录，不重写或搬动已有资源。'))
        layout.addWidget(row(QLabel(tr('ui.bc76b88fa2ea', '共享根目录（可选更改）')), path_field(self.shared_audio_root), button(tr('ui.81d3300ba5cf', '保存共享根目录'), self.save_shared_audio_root)))
        layout.addWidget(button(tr('ui.c8a3dedcb19a', '设置当前壁纸共享 / 专用目录…'), self.configure_resources))
        self.audio_library_status = hint(tr('ui.eb255c0f95b6', '选择此页或刷新时扫描；不会启动语音 API。'))
        layout.addWidget(self.audio_library_status)
        self.audio_library_tab_index = self.tabs.addTab(page, tr('ui.4f0534b98d95', '音频库'))
        self.rebuild_audio_sources()
        self.audio_scope.currentIndexChanged.connect(self.refresh_audio_library)
        self.audio_search.textChanged.connect(self.filter_audio_library)
        self.tabs.currentChanged.connect(self.audio_tab_changed)

    def audio_tab_changed(self, index):
        if index == self.audio_library_tab_index:
            self.refresh_audio_library()

    def rebuild_audio_sources(self):
        self.audio_sources = locations(self.store)
        for combo, include_all in [(self.audio_scope, True), (self.audio_target, False)]:
            previous = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            if include_all:
                combo.addItem(tr('ui.102bc7d451c2', '全部已配置目录'), "all")
            added = set()
            for source in self.audio_sources:
                if not include_all and source.get("read_only"):
                    continue
                key = source.get("scope", source["id"]) if include_all else source["id"]
                if key in added:
                    continue
                added.add(key)
                combo.addItem(source["label"], key)
                directories = [s["path"] for s in self.audio_sources if s.get("scope", s["id"]) == key] if include_all else [source["path"]]
                combo.setItemData(combo.count() - 1, "\n".join(directories), Qt.ItemDataRole.ToolTipRole)
            combo.setCurrentIndex(max(0, combo.findData(previous)))
            combo.blockSignals(False)

    def refresh_audio_library(self):
        if self.quitting:
            return
        if self.audio_library_busy:
            self.audio_refresh_pending = True
            return
        self.rebuild_audio_sources()
        selected = self.audio_scope.currentData()
        sources = copy.deepcopy([s for s in self.audio_sources if selected == "all" or s["id"] == selected or s.get("scope") == selected])
        self.audio_library_busy = True
        self.audio_library_status.setText(tr('ui.c8b1ab43128f', '正在后台扫描音频…'))
        self.submit(lambda: inventory(sources), lambda result: self.audio_library_scanned(result, selected), self.audio_library_error)

    def audio_library_scanned(self, result, scope=None):
        self.ensure_page(6)
        self.audio_library_busy = False
        if scope is not None and scope != self.audio_scope.currentData():
            self.audio_refresh_pending = False
            self.refresh_audio_library()
            return
        self.audio_records = result["records"]
        def value(record, column, role):
            if role == Qt.ItemDataRole.UserRole and column == 0:
                return record
            if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                return None
            values = [record["name"], "；".join(record["locations"]), str(len(record["profiles"])),
                      f"{record['bytes'] / 1024 / 1024:.2f} MB", record["path"]]
            if role == Qt.ItemDataRole.ToolTipRole:
                if column == 1:
                    return "\n".join(u["label"] + "\n" + u["directory"] for u in record.get("usages", [])) or values[column]
                if column == 3:
                    return tr('ui.aac6cffe85e4', '{value0:,} 字节（{value1}）', value0=record['bytes'], value1=values[column])
            return values[column]
        self.audio_table.set_records(self.audio_records, value)
        self.filter_audio_library(preserve_selection=True)
        self.audio_library_status.setText(tr('ui.349038c0569a', '{value0} 个音频文件；{value1} 项目录提示。共享文件按实际路径去重。', value0=len(self.audio_records), value1=len(result['warnings'])))
        if result["warnings"]:
            self.audio_library_status.setToolTip("\n".join(result["warnings"][:20]))
        else:
            self.audio_library_status.setToolTip("")
        if self.audio_refresh_pending:
            self.audio_refresh_pending = False
            self.refresh_audio_library()

    def audio_library_error(self, error):
        self.audio_library_busy = False
        self.audio_refresh_pending = False
        if hasattr(self.audio, "sync_bgm"):
            self.audio.sync_bgm()
        self.audio_library_status.setText(tr('ui.f2ea5b177673', '音频库操作失败：') + str(error))
        self.report_error(str(error))

    def filter_audio_library(self, *_args, preserve_selection=False):
        text = self.audio_search.text().strip().casefold()
        if not preserve_selection:
            self.audio_table.clearSelection()
        for index, record in enumerate(self.audio_records):
            self.audio_table.setRowHidden(index, bool(text and text not in (record["name"] + " " + " ".join(record["locations"]) + " " + record["path"]).casefold()))

    def selected_library_audio(self):
        return [self.audio_table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                for index in self.audio_table.selectionModel().selectedRows() if not self.audio_table.isRowHidden(index.row())]

    def select_library_audio(self, selected):
        from PySide6.QtCore import QItemSelectionModel
        self.audio_table.clearSelection()
        if selected:
            for index in range(self.audio_table.rowCount()):
                if not self.audio_table.isRowHidden(index):
                    self.audio_table.selectionModel().select(self.audio_table.model().index(index, 0),
                        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.audio_library_status.setText(tr('ui.cca6686a5c67', '已选择 {value0} 个音频；可批量复制或删除。', value0=len(self.selected_library_audio())))

    def preview_library_audio(self):
        records = self.selected_library_audio()
        if records:
            self.preview([Path(records[0]["path"])])

    def open_library_audio_folder(self):
        records = self.selected_library_audio()
        if not records:
            records = [self.audio_table.item(i, 0).data(Qt.ItemDataRole.UserRole)
                       for i in range(self.audio_table.rowCount()) if not self.audio_table.isRowHidden(i)][:1]
        if records:
            self.open_folder(str(Path(records[0]["path"]).parent))
            self.log(tr('ui.406e38253268', '已打开音频所在目录：') + str(Path(records[0]["path"]).parent))
        else:
            self.log(tr('ui.36a72ec62356', '当前列表没有音频，请先导入文件或调整筛选。'))

    def audio_target_path(self):
        source = next((s for s in self.audio_sources if s["id"] == self.audio_target.currentData()), None)
        if source is None:
            raise ValueError(tr('ui.c966fac44126', '请选择目标目录'))
        return destination(source["path"], self.audio_category.text(), self.store.protected())

    def audio_mutation_allowed(self):
        if self.tts_busy or self.audio_library_busy:
            self.report_error(tr('ui.a518a6a232c4', '请等待当前生成、扫描或复制结束后再管理文件。'))
            return False
        return True

    def import_library_audio(self):
        if not self.audio_mutation_allowed():
            return
        files, _ = QFileDialog.getOpenFileNames(self, tr('ui.0bb57eee7d00', '选择要复制导入的音频'), "", tr('ui.5dbdc98af8eb', '音频 (*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.wma *.opus)'))
        if files:
            self.copy_audio_paths(files)

    def copy_library_audio(self):
        if self.audio_mutation_allowed():
            self.copy_audio_paths([item["path"] for item in self.selected_library_audio()])

    def copy_audio_paths(self, paths):
        if not paths:
            return
        try:
            target = self.audio_target_path()
            protected = self.store.protected()
        except Exception as exc:
            self.report_error(str(exc))
            return
        self.audio_library_busy = True
        self.audio_library_status.setText(tr('ui.a8d3d8e8805c', '正在复制；同名文件自动编号，不覆盖原文件…'))
        self.submit(lambda: copy_audio(paths, target, protected), self.audio_files_changed, self.audio_library_error)

    def audio_files_changed(self, paths):
        self.audio_index.invalidate()
        self.audio_library_busy = False
        if hasattr(self.audio, "sync_bgm"):
            self.audio.sync_bgm()
        self.log(tr('ui.a430e7ac8c03', '音频库操作完成：{value0} 个文件。', value0=len(paths)))
        self.audio_refresh_pending = False
        self.refresh_audio_library()

    def reference_audio_target(self, key):
        if not self.editing_id or not self.audio_mutation_allowed():
            return
        try:
            target = self.audio_target_path()
            target.mkdir(parents=True, exist_ok=True)
            (self.voice_dir if key == "voice_dir" else self.bgm_dir).setText(str(target))
            if self.save_profile():
                if key == "voice_dir":
                    self.use_voice_dir()
                self.refresh_audio_library()
        except Exception as exc:
            self.report_error(str(exc))

    def recycle_library_audio(self):
        if not self.audio_mutation_allowed():
            return
        records = self.selected_library_audio()
        if not records:
            self.log(tr('ui.d7f33ca53784', '请先选择需要删除的音频，可使用全选或 Ctrl / Shift 多选。'))
            return
        if any(item.get("read_only") for item in records):
            self.report_error(tr('ui.2dd41648d6bc', '随附默认语音为只读资源，不能删除。可先复制到自己的音频目录再管理副本。'))
            return
        count = len({p for item in records for p in item["profiles"]})
        if QMessageBox.question(self, tr('ui.0da717ff7f49', '将音频移入回收站'), tr('ui.d7e0192b36ac', '将 {value0} 个文件移入系统回收站？\n涉及 {value1} 个配置的音频目录；共享文件移除后影响所有使用者，精确文件规则可能失效。\n配置和壁纸绑定保留，不会永久删除文件。', value0=len(records), value1=count), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        paths = [item["path"] for item in records]
        try:
            for path in paths:
                writable_path(path, self.store.protected())
            selected = {identity(path) for path in paths}
            for player in (self.audio.voice, self.audio.bgm):
                if identity(player.source().toLocalFile()) in selected:
                    player.stop()
                    from PySide6.QtCore import QUrl
                    player.setSource(QUrl())
        except Exception as exc:
            self.report_error(str(exc))
            return
        protected = self.store.protected()
        self.audio_library_busy = True
        self.submit(lambda: recycle_audio(paths, protected), self.audio_files_changed, self.audio_library_error)

    def save_shared_audio_root(self):
        if not self.audio_mutation_allowed():
            return
        previous = self.store.config.get("shared_asset_dir", "")
        try:
            if not self.editing_id and self.shared_dialogue_snapshot is not None and self.collect_dialogues() != self.shared_dialogue_snapshot:
                if not self.save_dialogue_library():
                    return
            value = self.shared_audio_root.text().strip()
            if value:
                value = str(writable_path(value, self.store.protected()))
            self.store.config["shared_asset_dir"] = value
            self.store.save()
            self.shared_audio_root.setText(str(shared_root(self.store)))
            self.log(tr('ui.f1b8d8c3e539', '共享根目录已保存；已有配置的目录绑定保持不变。'))
            self.refresh_audio_library()
            if not self.editing_id:
                self.load_shared_dialogue_library()
            if hasattr(self, "autosave"):
                self.autosave.remember("shared")
            return True
        except Exception as exc:
            self.store.config["shared_asset_dir"] = previous
            self.report_error(str(exc))
            return False
