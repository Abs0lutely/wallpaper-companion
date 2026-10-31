"""A unified audio library for shared folders and individual wallpaper bindings."""
import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

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
        layout.addWidget(hint("统一管理共享和各壁纸目录中的音频。直接引用目录不复制文件；需要专用副本时，可复制所选音频到目标目录。删除共享文件会影响所有引用它的配置。"))
        self.audio_scope = QComboBox()
        self.audio_search = QLineEdit()
        self.audio_search.setPlaceholderText("按文件名、路径或配置名称搜索…")
        layout.addWidget(row(QLabel("查看范围"), self.audio_scope, self.audio_search, button("刷新音频库", self.refresh_audio_library)))
        self.audio_table = QTableWidget(0, 5)
        self.audio_table.setHorizontalHeaderLabels(["文件名", "用途 / 目录", "引用配置数", "大小", "实际路径"])
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
        layout.addWidget(row(button("试听所选", self.preview_library_audio), button("停止试听", self.audio.voice.stop),
                             button("打开所选文件目录", self.open_library_audio_folder), button("移入回收站…", self.recycle_library_audio)))
        self.audio_target = QComboBox()
        self.audio_category = QLineEdit()
        self.audio_category.setPlaceholderText("可选分类子目录，例如：早安")
        layout.addWidget(row(QLabel("导入 / 复制目标"), self.audio_target, self.audio_category))
        layout.addWidget(row(button("导入音频文件…", self.import_library_audio), button("复制所选到目标", self.copy_library_audio)))
        layout.addWidget(row(button("目标目录用于当前壁纸语音", lambda: self.reference_audio_target("voice_dir")),
                             button("目标目录用于当前壁纸 BGM", lambda: self.reference_audio_target("bgm_dir"))))
        self.shared_audio_root = QLineEdit(str(shared_root(self.store)))
        self.shared_audio_root.setToolTip("默认位于当前数据目录的 audio/shared；修改只影响新绑定及下次显式选择共享目录，不重写已有路径。")
        layout.addWidget(row(QLabel("共享根目录（可选更改）"), path_field(self.shared_audio_root), button("保存共享根目录", self.save_shared_audio_root)))
        layout.addWidget(button("设置当前壁纸共享 / 专用目录…", self.configure_resources))
        self.audio_library_status = hint("选择此页或刷新时扫描；不会启动语音 API。")
        layout.addWidget(self.audio_library_status)
        self.audio_library_tab_index = self.tabs.addTab(page, "音频库")
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
                combo.addItem("全部已配置目录", "all")
            for source in self.audio_sources:
                combo.addItem(source["label"], source["id"])
                combo.setItemData(combo.count() - 1, source["path"], Qt.ItemDataRole.ToolTipRole)
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
        sources = copy.deepcopy([s for s in self.audio_sources if selected == "all" or s["id"] == selected])
        self.audio_library_busy = True
        self.audio_library_status.setText("正在后台扫描音频…")
        self.submit(lambda: inventory(sources), self.audio_library_scanned, self.audio_library_error)

    def audio_library_scanned(self, result):
        self.audio_library_busy = False
        self.audio_records = result["records"]
        self.audio_table.setRowCount(len(self.audio_records))
        for index, record in enumerate(self.audio_records):
            values = [record["name"], "；".join(record["locations"]), str(len(record["profiles"])),
                      f"{record['bytes'] / 1024 / 1024:.2f} MB", record["path"]]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record)
                self.audio_table.setItem(index, column, item)
        self.filter_audio_library()
        self.audio_library_status.setText(f"{len(self.audio_records)} 个音频文件；{len(result['warnings'])} 项目录提示。共享文件按实际路径去重。")
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
        self.audio_library_status.setText("音频库操作失败：" + str(error))
        self.report_error(str(error))

    def filter_audio_library(self):
        text = self.audio_search.text().strip().casefold()
        self.audio_table.clearSelection()
        for index in range(self.audio_table.rowCount()):
            self.audio_table.setRowHidden(index, bool(text and text not in " ".join(
                self.audio_table.item(index, c).text() for c in (0, 1, 4)).casefold()))

    def selected_library_audio(self):
        return [self.audio_table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                for index in self.audio_table.selectionModel().selectedRows() if not self.audio_table.isRowHidden(index.row())]

    def preview_library_audio(self):
        records = self.selected_library_audio()
        if records:
            self.preview([Path(records[0]["path"])])

    def open_library_audio_folder(self):
        records = self.selected_library_audio()
        if records:
            self.open_folder(str(Path(records[0]["path"]).parent))

    def audio_target_path(self):
        source = next((s for s in self.audio_sources if s["id"] == self.audio_target.currentData()), None)
        if source is None:
            raise ValueError("请选择目标目录")
        return destination(source["path"], self.audio_category.text(), self.store.protected())

    def audio_mutation_allowed(self):
        if self.tts_busy or self.audio_library_busy:
            self.report_error("请等待当前生成、扫描或复制结束后再管理文件。")
            return False
        return True

    def import_library_audio(self):
        if not self.audio_mutation_allowed():
            return
        files, _ = QFileDialog.getOpenFileNames(self, "选择要复制导入的音频", "", "音频 (*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.wma *.opus)")
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
        self.audio_library_status.setText("正在复制；同名文件自动编号，不覆盖原文件…")
        self.submit(lambda: copy_audio(paths, target, protected), self.audio_files_changed, self.audio_library_error)

    def audio_files_changed(self, paths):
        self.audio_library_busy = False
        if hasattr(self.audio, "sync_bgm"):
            self.audio.sync_bgm()
        self.log(f"音频库操作完成：{len(paths)} 个文件。")
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
            return
        count = len({p for item in records for p in item["profiles"]})
        if QMessageBox.question(self, "将音频移入回收站", f"将 {len(records)} 个文件移入系统回收站？\n涉及 {count} 个配置的音频目录；共享文件移除后影响所有使用者，精确文件规则可能失效。\n配置和壁纸绑定保留，不会永久删除文件。", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
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
            value = self.shared_audio_root.text().strip()
            if value:
                value = str(writable_path(value, self.store.protected()))
            self.store.config["shared_asset_dir"] = value
            self.store.save()
            self.shared_audio_root.setText(str(shared_root(self.store)))
            self.log("共享根目录已保存；已有配置的目录绑定保持不变。")
            self.refresh_audio_library()
        except Exception as exc:
            self.store.config["shared_asset_dir"] = previous
            self.report_error(str(exc))
