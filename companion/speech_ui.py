"""Honest item-level progress plus indeterminate current-stage activity."""
from .i18n import tr
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QProgressBar, QScrollArea


class SpeechFeedbackMixin:
    def build_speech_status(self, layout):
        self.tts_status = QLabel(tr('ui.ad64109e7c08', '尚未检测连接'))
        self.tts_status.setWordWrap(True)
        layout.addWidget(self.tts_status)
        self.tts_progress = QProgressBar()
        self.tts_progress.setRange(0, 1); self.tts_progress.setValue(0)
        self.tts_progress.setFormat(tr('ui.003402bb686b', '尚未开始生成'))
        layout.addWidget(self.tts_progress)
        self.tts_activity = QProgressBar()
        self.tts_activity.setRange(0, 0); self.tts_activity.setTextVisible(False)
        self.tts_activity.setMaximumHeight(6); self.tts_activity.hide()
        layout.addWidget(self.tts_activity)
        self.tts_stage_output = QPlainTextEdit()
        self.tts_stage_output.setReadOnly(True)
        self.tts_stage_output.setMaximumBlockCount(160)
        self.tts_stage_output.setMaximumHeight(100)
        self.tts_stage_output.setPlaceholderText(tr('ui.4b342dee2979', '这里显示准备接口、等待模型、合成、保存或失败阶段；不会估算模型内部百分比。'))
        layout.addWidget(self.tts_stage_output)

    def begin_generation(self, total):
        self.generation_started_at = time.monotonic()
        self.tts_progress.setRange(0, max(1, total)); self.tts_progress.setValue(0)
        self.tts_progress.setFormat(tr('ui.f61ae866a795', '%v / %m 条已处理（保存或跳过）'))
        self.tts_stage_output.clear(); self.tts_activity.show()
        self.generation_update(dict(completed=0, total=total, message=tr('ui.dfbbf482521f', '正在准备生成任务…')))
        QTimer.singleShot(0, self.reveal_generation_progress)

    def reveal_generation_progress(self):
        if not self.quitting and self.tabs.currentIndex() == 2:
            page = self.tabs.widget(2)
            if isinstance(page, QScrollArea):
                page.ensureWidgetVisible(self.tts_stage_output, 0, 16)

    def generation_update(self, event):
        if not self.tts_busy or self.quitting:
            return
        self.tts_progress.setRange(0, max(1, event["total"]))
        self.tts_progress.setValue(max(0, min(event["completed"], event["total"])))
        message = str(event["message"])
        self.tts_status.setText(message)
        elapsed = time.monotonic() - self.generation_started_at
        self.tts_stage_output.appendPlainText(f"[+{elapsed:.1f}s] {message}")

    def finish_generation_progress(self, success, message):
        self.tts_activity.hide()
        if success:
            self.tts_progress.setValue(self.tts_progress.maximum())
            self.tts_progress.setFormat(tr('ui.cb9cfd1b04f4', '%v / %m 条处理完成'))
        else:
            self.tts_progress.setFormat(tr('ui.324c7757e2a2', '已处理 %v / %m 条；任务未完成'))
        self.tts_stage_output.appendPlainText(str(message))
