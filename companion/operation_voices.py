"""Semantic UI speech using prepared clips only. Never starts or calls a TTS API."""
from .i18n import tr
import random
import time
import weakref
import shiboken6
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtWidgets import (QApplication, QAbstractButton, QAbstractSpinBox, QComboBox,
    QLineEdit, QPlainTextEdit, QAbstractSlider, QTableView)
from .action_lines import EVENT_LINES
from .core import ROOT, AUDIO_EXTENSIONS, filename_for


def classify_button(button):
    explicit = button.property("voiceEvent")
    if explicit in EVENT_LINES:
        return explicit
    from .i18n import source_text
    text = source_text(button.text().replace("&", ""))
    pairs = [("撤销|撤回", "undo"), ("恢复默认", "reset"), ("关闭自建|关闭接口", "api_stop"),
             ("启动本地|启动接口", "api_start"), ("生成", "generate"), ("停止试听|播放参考|试听", "preview"),
             ("下一首", "next"), ("继续", "resume"), ("暂停|停止", "pause"), ("保存", "save"),
             ("删除|回收站", "delete"), ("导入", "import"), ("导出", "export"), ("说明|手册", "help"),
             ("扫描|刷新|检测", "scan"), ("打开|浏览", "open"), ("新建|添加|新台词|补充|建立", "add"),
             ("编辑", "edit"), ("全选|不选|选择", "select")]
    import re
    for pattern, event in pairs:
        if re.search(pattern, text):
            return event
    if button.isCheckable():
        return "disable" if button.isChecked() else "enable"  # Called on press, before toggle.
    return "click"


from .operation_audio import scan_clips


class OperationVoices(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.w = window
        self.closed = False
        self.widgets = {}
        self.clips = {}
        self.last_play = -100.0
        self.last_events = {}
        self.rules = {}
        self.last_scan = -100.0
        self.scanning = False
        self.refresh_pending = False
        self.source = ""
        self.pending = None
        self.change_timer = QTimer(self); self.change_timer.setSingleShot(True)
        self.change_timer.timeout.connect(lambda: self.play(self.pending))
        QApplication.instance().installEventFilter(self)
        for button in [*window.navigation.values(), *window.home_buttons]:
            button.setProperty("voiceEvent", "navigate")
        for widget in window.findChildren(QObject):
            self.attach(widget)
        window.tabs.currentChanged.connect(lambda _: self.request("navigate"))
        window.profile_sections.currentChanged.connect(lambda _: self.request("navigate"))
        window.profiles.currentRowChanged.connect(lambda _: QTimer.singleShot(0, self.refresh))
        self.refresh()

    def owns(self, obj):
        while obj is not None and obj is not self.w:
            obj = obj.parentWidget() if hasattr(obj, "parentWidget") else None
        return obj is self.w

    def attach(self, widget):
        if not isinstance(widget, (QAbstractButton, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox, QAbstractSlider, QTableView)) or not self.owns(widget) or id(widget) in self.widgets:
            return
        key = id(widget); self.widgets[key] = widget
        widget.destroyed.connect(lambda *_: self.widgets.pop(key, None))
        ref = weakref.ref(widget)
        if isinstance(widget, QAbstractButton):
            widget.pressed.connect(lambda: self.request(classify_button(ref())) if ref() is not None and shiboken6.isValid(ref()) else None)
        elif isinstance(widget, QComboBox):
            widget.activated.connect(lambda _: self.request("select", delayed=True))
        elif isinstance(widget, QAbstractSlider):
            widget.sliderReleased.connect(lambda: self.request("change", delayed=True))
        elif isinstance(widget, QLineEdit):
            widget.textEdited.connect(lambda _: widget.setProperty("voiceEdited", True))
            widget.editingFinished.connect(lambda: self.finish_edit(ref()))
        elif isinstance(widget, QAbstractSpinBox):
            widget.editingFinished.connect(lambda: self.request("change", delayed=True) if widget.hasFocus() else None)
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(lambda: widget.setProperty("voiceEdited", True) if widget.hasFocus() else None)
        elif isinstance(widget, QTableView):
            widget.selectionModel().selectionChanged.connect(lambda *_: self.request("select", delayed=True) if widget.hasFocus() else None)

    def finish_edit(self, widget):
        if widget is not None and shiboken6.isValid(widget) and widget.property("voiceEdited"):
            widget.setProperty("voiceEdited", False)
            self.request("change", delayed=True)

    def eventFilter(self, obj, event):
        if not self.closed:
            if event.type() in (QEvent.Type.Show, QEvent.Type.Polish):
                self.attach(obj)
            elif event.type() == QEvent.Type.FocusOut and isinstance(obj, QPlainTextEdit) and self.owns(obj):
                self.finish_edit(obj)
        return False

    def refresh(self):
        if self.closed:
            return
        if self.scanning:
            self.refresh_pending = True
            return
        from .assets import shared_root
        from .operation_rules import config_payload
        from .bundled_audio import bundled_root
        rules = config_payload(self.w.store.config)["rules"]
        self.rules = {rule["event"]: rule for rule in rules}
        roots = [self.w.store.config.get("operation_voice_dir", ""), self.w.voice_dir.text().strip(),
                 shared_root(self.w.store) / "voice", bundled_root() / "operation-voice", bundled_root() / "operation-voice-ja-JP"]
        if self.w.store.config.get("operation_voice_pack_only", False):
            roots = [self.w.store.config.get("operation_voice_dir", "")]
        roots = [str(r) for r in roots if str(r).strip()]
        self.scanning = True; self.last_scan = time.monotonic()
        def ready(clips):
            self.scanning = False
            self.clips = clips
            count = sum(bool(paths) for paths in clips.values())
            if not self.w.page_pending(3):
                self.w.operation_voice_status.setText(tr('ui.21e1f8615b62', '操作语音：已找到 {value0}/{value1} 类。', value0=count, value1=len(EVENT_LINES)) + (tr('ui.1b0b41411191', '缺少的分类保持静音；请导入操作台词并生成音频。') if count < len(EVENT_LINES) else tr('ui.f9e30640af36', '已准备好。')))
            if self.refresh_pending:
                self.refresh_pending = False
                self.refresh()
        self.w.submit(lambda: scan_clips(roots, rules), ready, lambda error: self.scan_failed(error))

    def scan_failed(self, error):
        self.scanning = False
        if not self.w.page_pending(3):
            self.w.operation_voice_status.setText(tr('ui.476f066fd195', '操作语音读取失败：') + str(error))

    def request(self, event, delayed=False):
        if self.closed or not self.w.store.config.get("operation_voice_enabled", True) or not self.w.isVisible():
            return
        if time.monotonic() - self.last_scan > 10:
            self.refresh()
        if delayed:
            self.pending = event; self.change_timer.start(400)
        else:
            self.play(event)

    def play(self, event):
        w = self.w
        if self.closed or not w.isVisible() or not w.store.config.get("operation_voice_enabled", True) or w.paused or w.fullscreen or w.audio.busy:
            return
        rule = self.rules.get(event)
        if not rule or not rule["enabled"]:
            return
        now = time.monotonic()
        if now - self.last_play < w.store.config.get("operation_voice_min_interval", 1.2) or now - self.last_events.get(event, -100.0) < rule["cooldown"]:
            return
        files = self.clips.get(event) or []
        if not files:
            return
        self.source = random.choice(files)
        if Path(self.source).is_file():
            self.last_play = time.monotonic()
            self.last_events[event] = self.last_play
            w.audio.play_voice(self.source)

    def close(self):
        self.closed = True
        self.change_timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.widgets.clear()
