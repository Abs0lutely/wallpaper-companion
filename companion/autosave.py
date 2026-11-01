"""Navigation-bound autosave with guarded, one-step undo and a non-modal toast."""
import copy
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class Autosave(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.w = window
        self.busy = False
        self.closed = False
        self.last = None
        self.page = window.tabs.currentIndex()
        self.section = window.profile_sections.currentIndex()
        self.baseline = self.forms()
        self.toast = QFrame(window)
        self.toast.setObjectName("autosaveToast")
        self.toast.setStyleSheet("#autosaveToast {background:#3d3044; border:1px solid #edb2c4; border-radius:10px;} QLabel {color:#fff3fa;}")
        self.toast.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        layout = QHBoxLayout(self.toast)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.undo_button = QPushButton("撤销")
        self.undo_button.clicked.connect(self.undo)
        layout.addWidget(self.label, 1); layout.addWidget(self.undo_button)
        self.toast.hide()
        self.timer = QTimer(self); self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.toast.hide)
        window.tabs.currentChanged.connect(self.page_changed)
        window.profile_sections.currentChanged.connect(self.section_changed)

    def forms(self):
        w = self.w
        return dict(runtime=dict(ui_language=w.ui_language.currentData(), we_dir=w.we_dir.text().strip(), workshop_dir=w.workshop_dir.text().strip(),
                    monitor=w.monitor.value(), poll_seconds=w.poll_seconds.value(), ffprobe=w.ffprobe_path.text().strip(),
                    operation_voice_enabled=w.operation_voice_enabled.isChecked(), operation_voice_dir=w.operation_voice_dir.text().strip(),
                    **{k: c.currentData() for k, c in w.backend_combos.items()},
                    enabled_plugins=[w.plugin_list.item(i).text() for i in range(w.plugin_list.count())
                                     if w.plugin_list.item(i).checkState() == Qt.CheckState.Checked]),
                    tts=(w.provider_choice.currentData(), w.tts_settings(), w.filename_model.text().strip()),
                    shared=w.shared_audio_root.text().strip(), roots=w.extra_library_roots.toPlainText())

    def remember(self, key):
        if hasattr(self, "baseline"):
            self.baseline[key] = self.forms()[key]

    def files_before(self):
        from .assets import shared_root
        w = self.w
        value = w.dialogue_file.text().strip() if w.editing_id else str(shared_root(w.store) / "dialogues.json")
        if not value:
            return {}
        from .core import writable_path
        path = writable_path(value, w.store.protected())
        return {path: path.read_bytes() if path.exists() else None}

    def show(self, message):
        self.w.log(message)
        if not self.w.isVisible():
            return
        self.label.setText(message)
        self.undo_button.setEnabled(self.last is not None)
        self.toast.setFixedWidth(min(750, max(300, self.w.width() - 60)))
        self.toast.adjustSize()
        self.toast.move((self.w.width() - self.toast.width()) // 2, max(12, self.w.height() - self.toast.height() - 70))
        self.toast.show(); self.toast.raise_(); self.timer.start(6500)

    def record(self, before, files, message):
        after = copy.deepcopy(self.w.store.config)
        changes = {k: (copy.deepcopy(before.get(k)), copy.deepcopy(after.get(k)))
                   for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
        changed_files = {p: (data, p.read_bytes() if p.exists() else None)
                         for p, data in files.items() if data != (p.read_bytes() if p.exists() else None)}
        if changes or changed_files:
            self.last = changes, changed_files
            self.show(message)
            if hasattr(self.w, "operation_voices"):
                self.w.operation_voices.request("save")
            return True
        return False

    def flush(self):
        if self.busy or self.closed or self.w.quitting:
            return True
        w = self.w
        self.busy = True
        before = copy.deepcopy(w.store.config)
        baseline = copy.deepcopy(self.baseline)
        files = {}
        try:
            forms = self.forms()
            profile_dirty = bool(w.editing_id and w.draft_profile() != w.store.profile(w.editing_id))
            shared_dirty = not w.editing_id and w.shared_dialogue_snapshot is not None and w.collect_dialogues() != w.shared_dialogue_snapshot
            if profile_dirty or shared_dirty:
                files = self.files_before()
                if not (w.save_profile() if profile_dirty else w.save_dialogue_library()):
                    raise ValueError("配置或台词未保存，编辑内容仍保留。请修正后重试。")
            if forms["runtime"] != self.baseline["runtime"]:
                if not w.save_settings():
                    raise ValueError("运行设置未保存。")
            if forms["tts"] != self.baseline["tts"]:
                if not w.save_tts():
                    raise ValueError("接口设置未保存。")
            if forms["roots"] != self.baseline["roots"]:
                if not w.save_library_roots():
                    raise ValueError("壁纸库目录未保存。")
            if forms["shared"] != self.baseline["shared"]:
                if not w.save_shared_audio_root():
                    raise ValueError("共享根目录未保存。")
            self.baseline = self.forms()
            recorded = self.record(before, files, "已自动保存修改。可撤销本次自动保存。")
            if not recorded and forms != baseline:
                self.last = None
                self.show("设置已自动保存，没有可撤销的配置差异；接口密钥不参与撤销。")
            return True
        except Exception as exc:
            # Never leave an in-memory unsaved draft looking like a persisted config.
            w.store.config = before
            self.baseline = baseline
            try:
                self.restore_files(files)
                if w.store.path.exists():
                    w.store.save()
            except Exception as rollback:
                w.log("保存回退失败，保留编辑内容，请检查文件权限：" + str(rollback))
            w.poll.setInterval(before.get("poll_seconds", 4) * 1000)
            w.log("自动保存未完成：" + str(exc))
            self.show("自动保存失败：编辑仍保留，请修正错误后重试。")
            return False
        finally:
            self.busy = False

    @staticmethod
    def restore_files(files):
        for path, data in files.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                temp = path.with_suffix(path.suffix + ".undo.tmp")
                temp.write_bytes(data); temp.replace(path)

    def page_changed(self, index):
        if self.busy:
            return
        old = self.page
        if self.flush():
            self.page = index
        else:
            self.w.tabs.blockSignals(True)
            self.w.tabs.setCurrentIndex(old)
            self.w.tabs.blockSignals(False)
            self.w.shell_page_changed(old)

    def section_changed(self, index):
        if self.busy:
            return
        if self.flush():
            self.section = index
        else:
            self.w.profile_sections.blockSignals(True)
            self.w.profile_sections.setCurrentIndex(self.section)
            self.w.profile_sections.blockSignals(False)
            self.w.shell_page_changed(self.w.tabs.currentIndex())

    def undo(self):
        w = self.w
        if not self.last:
            w.log("没有可撤销的自动保存。")
            return False
        if self.busy:
            return False
        changes, files = self.last
        current = copy.deepcopy(w.store.config)
        try:
            forms = self.forms()
            if forms != self.baseline or (w.editing_id and w.draft_profile() != w.store.profile(w.editing_id)) or (not w.editing_id and w.collect_dialogues() != w.shared_dialogue_snapshot):
                raise ValueError("有新的编辑尚未保存，请先保存；不会用撤销覆盖新的修改。")
            if any(current.get(k) != after for k, (_, after) in changes.items()) or any((p.read_bytes() if p.exists() else None) != after for p, (_, after) in files.items()):
                raise ValueError("相关配置或台词已再次改变，不能覆盖后续修改。")
            self.busy = True
            for k, (before, _) in changes.items():
                w.store.config[k] = copy.deepcopy(before)
            self.restore_files({p: before for p, (before, _) in files.items()})
            w.store.save()
            selected = w.editing_id
            w.refresh_profiles(selected); w.load_settings(); w.load_tts()
            from .assets import shared_root
            w.shared_audio_root.setText(str(shared_root(w.store)))
            w.extra_library_roots.setPlainText("\n".join(w.store.config.get("library_roots", [])))
            w.activate_profile(force=True)
            w.apply_appearance()
            w.hover_help.set_enabled(w.store.config["hover_help"])
            w.help_button.setText("悬停说明：开启" if w.store.config["hover_help"] else "悬停说明：关闭")
            w.poll.setInterval(w.poll_seconds.value() * 1000)
            if hasattr(w, "operation_voices"):
                w.operation_voices.refresh()
            self.baseline = self.forms()
            self.last = None
            self.show("已撤销上一次自动保存。接口密钥不参与撤销。")
            if hasattr(w, "operation_voices"):
                w.operation_voices.request("undo")
            return True
        except Exception as exc:
            w.store.config = current
            try:
                if self.busy:
                    self.restore_files({p: after for p, (_, after) in files.items()})
                    w.store.save()
            except OSError as rollback:
                w.log("撤销回退失败：" + str(rollback))
            w.report_error("无法撤销：" + str(exc))
            return False
        finally:
            self.busy = False

    def close(self):
        self.closed = True
        self.timer.stop(); self.toast.hide()
