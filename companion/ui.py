from __future__ import annotations

import copy
import os
import random
import time
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QTime, Signal, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QStyle, QSystemTrayIcon, QTabWidget, QTableWidget,
    QTableWidgetItem, QTimeEdit, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView,
)
from .file_dialogs import FileDialogs as QFileDialog

from .i18n import tr, language
from .core import DATA, ROOT, PLUGIN_DIR, Store, RuleEngine, audio_files, candidates, identity, new_profile, new_rule, writable_path
from .audio import Audio
from .services import InputHooks, api_status, current_wallpaper, foreground_state, generate, start_api
from .extensions import load_extensions
from .library_ui import LibraryMixin, DialogueMixin
from .audio_library_ui import AudioLibraryMixin
from .characters_ui import CharacterMixin
from .speech_ui import SpeechFeedbackMixin
from .generation_ui import GenerationReviewMixin
from .binding_ui import DialogueBindingMixin
from .mode_ui import ModeMixin

EVENTS = {
    "key": tr('ui.ee2638183d3e', '快捷键'), "mouse_left": tr('ui.2c3c432593de', '鼠标左键'), "mouse_right": tr('ui.12b284d44fff', '鼠标右键'), "mouse_middle": tr('ui.43645a86c3b9', '鼠标中键'),
    "mouse_x1": tr('ui.8789ecb5ac8f', '鼠标侧键 X1'), "mouse_x2": tr('ui.fd14b5b27ab3', '鼠标侧键 X2'), "scroll_up": tr('ui.4b0e0ffc8a09', '滚轮向上'), "scroll_down": tr('ui.a1fa3ac26b5d', '滚轮向下'),
    "any_key": tr('ui.1e57f195c63a', '任意按键'), "random": tr('ui.17ee7b24f561', '定时随机'), "startup": tr('ui.1e33da357454', '绑定的壁纸开始播放'),
    "scheduled": tr('ui.9be12cf9eff4', '每天固定时刻'),
}

from .theme_ui import stylesheet
from .shell_ui import CompanionShellMixin

STYLE = stylesheet()


def button(text, fn, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    if getattr(fn,"__name__","") in {"bind_current","bind_profile"}:b.setProperty("requiresWE",True)
    b.clicked.connect(fn)
    return b


def spin(low, high, value, suffix=""):
    w = QSpinBox()
    w.setRange(low, high)
    w.setValue(value)
    w.setSuffix(suffix)
    return w


def hint(text):
    w = QLabel(text)
    w.setObjectName("subtle")
    w.setWordWrap(True)
    return w


def row(*widgets):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return container


def path_field(line, directory=True, title=tr('ui.0d6fad8138e7', '选择文件夹')):
    def choose():
        if directory:
            value = QFileDialog.getExistingDirectory(line, title, line.text())
        else:
            value, _ = QFileDialog.getOpenFileName(line, title, line.text(), tr('ui.663b66033d11', '所有文件 (*)'))
        if value:
            line.setText(value)
    return row(line, button(tr('ui.0617557e7bbc', '浏览…'), choose))


def app_icon():
    for name in ("app-icon.ico", "app-icon.png"):
        icon = QIcon(str(ROOT / "readme-assets" / name))
        if not icon.isNull():
            return icon
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)


from .rules_ui import RuleDialog


class Window(ModeMixin, DialogueBindingMixin, LibraryMixin, DialogueMixin, AudioLibraryMixin, CharacterMixin, SpeechFeedbackMixin, GenerationReviewMixin, CompanionShellMixin, QMainWindow):
    job_done = Signal(object, object, object)
    hook_event = Signal(str, str)
    progress = Signal(str)
    generation_state = Signal(object)
    api_stage = Signal(str)

    def __init__(self, store=None, hooks=True):
        super().__init__()
        self.store = store or Store()
        self.setWindowTitle(tr('ui.b9fcd7be6aa6', '壁纸声伴 · Wallpaper Companion'))
        self.setWindowIcon(app_icon())
        self.resize(1180, 840)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1180, available.width() - 60), min(840, available.height() - 60))
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="companion")
        self.job_done.connect(self.finish_job)
        self.progress.connect(self.log)
        self.generation_state.connect(self.generation_update)
        self.api_stage.connect(self.api_message)
        self.mode_epoch=0
        self.query_busy = False
        self.tts_busy = False
        self.api_busy = False
        self.generation_cancel = threading.Event()
        self.quitting = False
        self.editing_id = None
        self.edit_private_root = ""
        self.edit_rules = []
        self.active_id = None
        self.current = dict(path="", title=tr('ui.3fe60d153ef1', '正在检测当前壁纸…'), running=False)
        self.current_display_text = tr('ui.e8b970bc3e05', '正在检测…')
        self.current_display_tooltip = ""
        self.paused = False
        self.fullscreen = False
        self.original_audio = dict(state="unknown", detail=tr('ui.420b7c1e3709', '尚未检测原壁纸音频'))
        self.original_audio_request = 0
        self.engine = RuleEngine()
        self.registry = load_extensions(self.store.config)
        for setting, mapping, fallback in [("audio_backend", self.registry.audio, "qt"),
                                           ("input_backend", self.registry.inputs, "pynput"),
                                           ("wallpaper_backend", self.registry.wallpapers, "wallpaper_engine"),
                                           ("library_backend", self.registry.libraries, "wallpaper_engine"),
                                           ("audio_detector", self.registry.audio_detectors, "builtin")]:
            if self.store.config.get(setting) not in mapping:
                self.registry.errors.append(tr('ui.a3a3a2d7f567', '所选扩展不可用，已回退：') + setting)
                self.store.config[setting] = fallback
        EVENTS.clear()
        EVENTS.update({key: value[0] for key, value in self.registry.events.items()})
        self.audio = self.registry.audio[self.store.config.get("audio_backend", "qt")][1](self)
        self.audio.message.connect(self.log)
        self.hooks = self.registry.inputs[self.store.config.get("input_backend", "pynput")][1](lambda event, key: self.hook_event.emit(event, key))
        self.hook_event.connect(self.input_event)
        self.build_ui()
        self.build_tray()
        self.wrap_form_labels()
        self.refresh_profiles()
        self.load_settings()
        self.load_tts()
        from .feedback import ActionFeedback
        self.action_feedback = ActionFeedback(self)
        from .motion import ButtonMotion
        self.button_motion = ButtonMotion(self)
        from .help_ui import HoverHelp
        self.hover_help = HoverHelp(self)
        from .autosave import Autosave
        self.autosave = Autosave(self)
        self.bgm_enabled.toggled.connect(self.bgm_enabled_changed)
        from .operation_voices import OperationVoices
        self.operation_voices = OperationVoices(self)
        for error in self.registry.errors:
            self.log(tr('ui.96f66c64d189', '扩展加载失败：') + error)
        self.audio.changed.connect(self.refresh_status)
        if hooks:
            try:
                self.hooks.start()
            except Exception as exc:
                self.log(tr('ui.44c1f4a1c87e', '输入监听未启动：') + str(exc))
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.detect)
        if not self.is_standalone():self.poll.start(self.store.config.get("poll_seconds", 4) * 1000)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self.on_tick)
        self.tick.start(1000)
        self.apply_run_mode()
        if self.is_standalone():self.activate_profile(force=True)
        QTimer.singleShot(200, self.detect)
        QTimer.singleShot(500, self.scan_library)

    def wrap_form_labels(self):
        for form in self.findChildren(QFormLayout):
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            for i in range(form.rowCount()):
                item = form.itemAt(i, QFormLayout.ItemRole.LabelRole)
                if item and isinstance(item.widget(), QLabel):
                    item.widget().setWordWrap(True)

    def build_ui(self):
        self.build_companion_shell()

    def build_profile_tab(self):
        from .profile_ui import build_profile
        build_profile(self)

    def build_tts_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.provider_choice = QComboBox()
        for provider in self.registry.speech.values():
            self.provider_choice.addItem(provider.title, provider.id)
        layout.addWidget(row(QLabel(tr('ui.a206f5bbafdb', '语音生成扩展')), self.provider_choice))
        self.provider_description = hint("")
        layout.addWidget(self.provider_description)
        provider_scroll = QScrollArea()
        provider_scroll.setWidgetResizable(True)
        self.provider_fields_widget = QWidget()
        self.provider_form = QFormLayout(self.provider_fields_widget)
        self.provider_widgets = {}
        self.provider_cache = {}
        self.rendered_provider = ""
        layout.addWidget(self.build_character_tools())
        provider_scroll.setWidget(self.provider_fields_widget)
        layout.addWidget(provider_scroll, 2)
        self.tts_output = QLineEdit()
        layout.addWidget(row(QLabel(tr('ui.57c076598349', '生成保存目录')), path_field(self.tts_output)))
        self.filename_model = QLineEdit()
        self.filename_model.setMaxLength(200)
        self.filename_model.setToolTip(tr('ui.0b8f27bb4646', '仅影响新音频的文件名，不会切换模型。留空按匹配的角色预设、权重名或服务模型/音色推断；外部 API 未指定模型时标为未指定模型。'))
        self.filename_model.setPlaceholderText(tr('ui.484f6c435a90', '留空按当前角色 / 权重 / 服务模型和音色推断；无法确定时使用“未指定模型”'))
        layout.addWidget(row(QLabel(tr('ui.920347c27382', '文件名中的模型标签')), self.filename_model))
        self.skip_existing_tts_audio = QCheckBox(tr('ui.2ba6c6b0d711', '跳过已存在的同名音频（生成前仍会确认）'))
        self.skip_existing_tts_audio.setChecked(True)
        layout.addWidget(self.skip_existing_tts_audio)
        self.transferred_dialogues = None
        self.transferred_lines = ""
        self.start_api_button = button(tr('ui.44f396b9cc0c', '启动本地 API'), self.launch_api)
        self.check_api_button = button(tr('ui.ab4acf8e35de', '检测连接'), self.check_api)
        layout.addWidget(row(button(tr('ui.03b147f610ea', '保存接口设置'), self.save_tts), self.check_api_button,
                             self.start_api_button, button(tr('ui.327fc807c3e1', '使用当前配置的语音目录'), self.use_voice_dir)))
        self.reference_preview_button = button(tr('ui.040fcb406728', '播放参考音频'), self.preview_reference_audio)
        layout.addWidget(row(self.reference_preview_button, button(tr('ui.ede34e7bad0a', '停止参考试听'), self.audio.voice.stop)))
        layout.addWidget(hint(tr('ui.582ac431fea1', '每行一条台词，按台词保存 WAV，重名自动编号。密钥保存到系统凭据管理器；切换服务可分别保存设置。')))
        self.lines = QPlainTextEdit()
        self.lines.setPlaceholderText(tr('ui.dd2a658dee35', '欢迎回来。\n今天也辛苦了。\n早上好，新的一天开始啦。'))
        layout.addWidget(self.lines, 1)
        self.generate_button = button(tr('ui.45295cc8574e', '生成并保存语音'), self.generate_audio, True)
        layout.addWidget(row(self.generate_button, button(tr('ui.de285e9d2d36', '打开保存目录'), lambda: self.open_folder(self.tts_output.text()))))
        self.build_speech_status(layout)
        self.lines.textChanged.connect(self.transferred_text_changed)
        self.tabs.addTab(page, tr('ui.4c403b5c0b50', '生成语音'))
        self.provider_choice.currentIndexChanged.connect(self.switch_provider)

    def stash_provider(self):
        if self.rendered_provider:
            values = {}
            for key, widget in self.provider_widgets.items():
                if isinstance(widget, QPlainTextEdit):
                    values[key] = widget.toPlainText().strip()
                elif isinstance(widget, QDoubleSpinBox):
                    values[key] = widget.value()
                elif hasattr(widget,"code"):
                    values[key] = widget.code()
                elif isinstance(widget, QComboBox):
                    values[key] = widget.currentText().strip()
                elif isinstance(widget, QCheckBox):
                    values[key] = widget.isChecked()
                else:
                    values[key] = widget.text().strip()
            self.provider_cache[self.rendered_provider] = values

    def switch_provider(self):
        self.stash_provider()
        provider = self.registry.speech[self.provider_choice.currentData()]
        while self.provider_form.rowCount():
            self.provider_form.removeRow(0)
        self.provider_widgets = {}
        self.rendered_provider = provider.id
        values = self.provider_cache.get(provider.id, {})
        for field in provider.fields:
            value = values.get(field.key, field.default)
            if field.kind == "multiline":
                widget = QPlainTextEdit(str(value))
                widget.setMaximumHeight(70)
            elif field.kind == "float":
                widget = QDoubleSpinBox()
                widget.setRange(.5, 2)
                widget.setSingleStep(.1)
                widget.setValue(float(value))
            elif field.kind == "bool":
                widget = QCheckBox()
                widget.setChecked(value is True)
            elif field.kind == "language":
                from .language_checks import LanguageCombo
                widget=LanguageCombo(str(value))
            elif field.kind in {"gpt_model", "sovits_model"}:
                widget = QComboBox()
                widget.setEditable(True)
                widget.setMinimumContentsLength(16)
                widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                widget.addItem("")
                widget.setCurrentText(str(value))
                widget.lineEdit().setPlaceholderText(tr('ui.0d5449c08f83', '留空沿用当前模型；可扫描选择或浏览'))
            else:
                widget = QLineEdit(str(value))
                if field.kind == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
                    if not value:
                        try:
                            from .secrets import read_secret
                            widget.setText(read_secret(provider.id if field.key == "api_key" else provider.id + ":" + field.key))
                        except Exception as exc:
                            self.log(tr('ui.2150989dc6c5', '无法读取系统密钥存储：') + str(exc))
            from .help_ui import PROVIDER_HELP
            widget.setToolTip(field.help or PROVIDER_HELP.get(field.key, tr('ui.8ffcd6932fc7', '填写“') + field.label + tr('ui.e14b972b721c', '”，参数由此语音扩展定义。')))
            if isinstance(widget, QLineEdit):
                widget.setPlaceholderText(field.help)
            if field.key in {"reference","python"}:widget.setProperty("projectRelative",True)
            self.provider_widgets[field.key] = widget
            display = path_field(widget, field.kind == "directory") if field.kind in {"file", "directory"} else widget
            if field.kind in {"gpt_model", "sovits_model"}:
                display = self.model_path_field(widget)
            self.provider_form.addRow(field.label, display)
        self.provider_description.setText(provider.description)
        self.start_api_button.setVisible(provider.start is not None or provider.id == "gpt_sovits")
        self.update_api_controls()
        self.character_provider_changed()
        from .help_ui import annotate_controls
        annotate_controls(self)

    def build_settings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.run_mode=QComboBox()
        self.run_mode.addItem(tr("mode.we","跟随 Wallpaper Engine"),"wallpaper_engine")
        self.run_mode.addItem(tr("mode.standalone","独立声音伴随"),"standalone")
        form.addRow(tr("mode.label","运行模式"),self.run_mode)
        self.run_mode.currentIndexChanged.connect(self.change_run_mode)
        self.mode_notice=hint("");form.addRow(self.mode_notice)
        self.ui_language = QComboBox()
        self.ui_language.addItem("简体中文", "zh-CN")
        self.ui_language.addItem("English", "en-US")
        self.ui_language.setToolTip(tr("settings.language_next_start", "界面语言将在下次启动时生效。"))
        form.addRow(tr("settings.language", "界面语言 / Interface language"), self.ui_language)
        self.language_notice = hint("")
        form.addRow(self.language_notice)
        self.ui_language.currentIndexChanged.connect(self.refresh_language_notice)
        self.we_dir = QLineEdit()
        self.workshop_dir = QLineEdit()
        self.monitor = spin(0, 20, 0)
        self.poll_seconds = spin(2, 60, 4, tr('ui.00fe8dda1fd7', ' 秒'))
        self.backend_combos = {}
        for setting, title, mapping in [("wallpaper_backend", tr('ui.eed49e677fcc', '壁纸识别扩展'), self.registry.wallpapers),
                                         ("audio_backend", tr('ui.cc3d927018b7', '音频播放扩展'), self.registry.audio),
                                         ("input_backend", tr('ui.6db0f0ae7e79', '输入事件扩展'), self.registry.inputs),
                                         ("library_backend", tr('ui.a9d308b8b573', '壁纸库扫描扩展'), self.registry.libraries),
                                         ("audio_detector", tr('ui.cf5e10d4ef4a', '原壁纸声音检测扩展'), self.registry.audio_detectors)]:
            combo = QComboBox()
            for identifier, (label, _) in mapping.items():
                combo.addItem(label, identifier)
            combo.setToolTip(title + tr('ui.0868be683c6f', '：选择已加载的后端，保存后重启应用。'))
            self.backend_combos[setting] = combo
            form.addRow(title, combo)
        form.addRow(tr('ui.af63118b14ac', 'WE 安装目录（只读使用）'), path_field(self.we_dir))
        form.addRow(tr('ui.9a3a53179e09', '工坊目录（写入保护）'), path_field(self.workshop_dir))
        form.addRow(tr('ui.129a9bbc68bc', '跟随显示器（从 0 开始）'), self.monitor)
        form.addRow(tr('ui.766431c1996b', '壁纸检测间隔'), self.poll_seconds)
        layout.addLayout(form)
        layout.addWidget(button(tr('ui.be1f0d30be41', '保存运行设置'), self.save_settings, True))
        layout.addWidget(row(button(tr('ui.3d55c6886570', '撤销最近自动保存'), lambda: self.autosave.undo()),
                             button(tr('ui.99845b14dc23', '恢复默认配置…'), self.restore_defaults)))
        self.operation_voice_enabled = QCheckBox(tr('ui.d3cb2801d30f', '播放操作回应语音（默认开启）'))
        self.operation_voice_enabled.toggled.connect(self.toggle_operation_voice)
        self.operation_voice_dir = QLineEdit()
        self.operation_voice_dir.setPlaceholderText(tr('ui.1d78040f7b21', '留空：共享语音目录，再查找随程序附带的操作语音包'))
        self.operation_voice_status = hint(tr('ui.524c211e0e7b', '操作语音尚未扫描。'))
        layout.addWidget(self.operation_voice_enabled)
        layout.addWidget(button(tr('ui.b00caf4fe520', '操作回应规则…'), self.configure_operation_rules))
        layout.addWidget(row(QLabel(tr('ui.c0dccd9c99ab', '操作语音目录（可选）')), path_field(self.operation_voice_dir),
                             button(tr('ui.120494ddaf90', '刷新操作语音'), lambda: self.operation_voices.refresh())))
        layout.addWidget(self.operation_voice_status)
        layout.addWidget(button(tr('ui.6e2442e35392', '导入默认操作台词'), self.add_operation_dialogues))
        self.startup_button = button(tr('ui.ee03b4e6df70', '检测开机自启状态…'), self.toggle_startup)
        layout.addWidget(self.startup_button)
        from .startup import startup_enabled
        try:
            self.refresh_startup_button(startup_enabled())
        except OSError as exc:
            self.startup_button.setText(tr('ui.d216b7683bab', '开机自启状态读取失败（点击重试）'))
        self.ffprobe_path = QLineEdit(self.store.config.get("ffprobe", ""))
        layout.addWidget(row(QLabel(tr('ui.5f78f3444460', 'ffprobe（留空自动发现）')), path_field(self.ffprobe_path, False)))
        layout.addWidget(QLabel(tr('ui.3650757f4e48', '本地扩展（勾选后保存，重启生效）')))
        self.plugin_list = QListWidget()
        self.plugin_list.setMaximumHeight(110)
        from PySide6.QtWidgets import QListWidgetItem
        plugin_directory = PLUGIN_DIR
        for plugin in sorted(plugin_directory.glob("*.py")) if plugin_directory.exists() else []:
            item = QListWidgetItem(plugin.stem)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if plugin.stem in self.store.config.get("enabled_plugins", []) else Qt.CheckState.Unchecked)
            self.plugin_list.addItem(item)
        layout.addWidget(self.plugin_list)
        layout.addWidget(hint(tr('ui.5e7bac498bea', '从可信来源将扩展 .py 文件放入下方按钮打开的目录后重启即可列出。启用的 Python 扩展拥有本程序的文件/网络权限。内置功能无需勾选。')))
        layout.addWidget(button(tr('ui.694b1a5b1af9', '打开扩展目录'), lambda: self.open_folder(str(PLUGIN_DIR))))
        layout.addWidget(hint(tr('ui.61bc0896f0ad', '自动识别只读轮询 WE 保存的选择；点击立即检测时才尝试官方 getWallpaper 命令。\n不运行修改壁纸、音量或暂停 WE 的命令。\n伴随暂停和全屏静音只控制本程序的声音。每次只跟随一台显示器。\n\n关闭窗口会最小化到托盘；右键托盘图标可以暂停或退出。\n开机自启由上方按钮选择，仅当前用户登录后运行；不记录键盘文本。云端语音发送台词至配置的服务。\n\n配置位置：{value0}\n复用开源组件：PySide6 / Qt Multimedia、pynput、requests、psutil。来源见 THIRD_PARTY.md。', value0=DATA / 'config.json')))
        layout.addWidget(row(button(tr('ui.f99dce8769e3', '打开程序数据目录'), lambda: self.open_folder(str(DATA))),
                             button(tr('ui.4eaafd3ffbce', '打开使用说明'), lambda: self.open_document("USAGE.md"))))
        layout.addStretch()
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setWidget(page)
        self.tabs.addTab(settings_scroll, tr('ui.078e20eb558e', '运行设置'))

    def build_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip(tr('ui.2728fc2e4d60', '壁纸声伴 · 配置与音频伴随'))
        menu = QMenu(self)
        menu.addAction(tr('ui.514d8331f14c', '打开配置'), self.show_window)
        self.tray_pause = menu.addAction(tr('ui.a555aecaab24', '暂停伴随'), self.toggle_pause)
        menu.addAction(tr('ui.68a284b91eed', '暂停 / 继续 BGM'), self.toggle_bgm)
        menu.addAction(tr('ui.7e87c201c7ab', '下一首 BGM'), self.audio.next_bgm)
        menu.addSeparator()
        menu.addAction(tr('ui.498e1d59b4d7', '退出'), self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def log(self, text):
        if hasattr(self, "action_feedback"):
            self.action_feedback.show_message(text)
        self.logs.appendPlainText(datetime.now().strftime("%H:%M:%S") + "  " + str(text))

    def submit(self, task, callback, error=None):
        future = self.executor.submit(task)
        def done(f):
            if self.quitting:
                return
            try:
                result = f.result()
                self.job_done.emit(callback, result, None)
            except Exception as exc:
                if not self.quitting:
                    self.job_done.emit(error or self.report_error, None, str(exc))
        future.add_done_callback(done)

    def finish_job(self, callback, result, error):
        if not self.quitting:
            callback(error if error is not None else result)

    def report_error(self, error):
        if hasattr(self, "operation_voices"):
            self.operation_voices.request("error")
        self.log(tr('ui.2227758ede17', '错误：') + str(error))
        QMessageBox.warning(self, tr('ui.79be13bdf0c5', '操作未完成'), str(error))

    def refresh_profiles(self, selected=None):
        selected = selected or (self.store.config.get("standalone_profile") if self.is_standalone() else self.editing_id)
        self.profiles.blockSignals(True)
        self.profiles.clear()
        target = -1
        for i, p in enumerate(self.store.config["profiles"]):
            self.profiles.addItem(p["name"] + ("" if self.is_standalone() else (tr('ui.2cdc4d329d40', '  · 已绑定') if p["wallpaper"] else tr('ui.8cd409330491', '  · 未绑定'))))
            self.profiles.item(i).setData(Qt.ItemDataRole.UserRole, p["id"])
            if p["id"] == selected:
                target = i
        if target < 0 and self.profiles.count():
            target = 0
        self.profiles.setCurrentRow(target)
        self.profiles.blockSignals(False)
        self.select_profile(target)
        self.refresh_shell()
        self.manual.blockSignals(True)
        self.manual.setChecked(bool(self.store.config["manual_profile"]))
        self.manual.blockSignals(False)

    def select_profile(self, index):
        old_voice_dir = self.voice_dir.text()
        old = self.store.profile(self.editing_id)
        profiles = self.store.config["profiles"]
        new_id = profiles[index]["id"] if 0 <= index < len(profiles) else None
        if not old and new_id and self.shared_dialogue_snapshot is not None and self.collect_dialogues() != self.shared_dialogue_snapshot:
            saved = self.autosave.flush() if hasattr(self, "autosave") and not self.autosave.busy else self.save_dialogue_library()
            if not saved:
                self.profiles.blockSignals(True)
                self.profiles.setCurrentRow(-1)
                self.profiles.blockSignals(False)
                return
        if old and old["id"] != new_id and hasattr(self, "autosave") and not self.autosave.busy:
            if not self.autosave.flush():
                self.profiles.blockSignals(True)
                self.profiles.setCurrentRow(next(i for i, p in enumerate(profiles) if p["id"] == old["id"]))
                self.profiles.blockSignals(False)
                return
            profiles = self.store.config["profiles"]
            self.profiles.blockSignals(True)
            self.profiles.setCurrentRow(index)
            self.profiles.blockSignals(False)
        elif old and old["id"] != new_id and not hasattr(self, "autosave") and self.draft_profile() != old:
            response = QMessageBox.question(self, tr('ui.47cbb648eede', '配置尚未保存'), tr('ui.fc8d72fbefb1', '当前修改尚未保存。放弃修改并切换配置？'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if response != QMessageBox.StandardButton.Yes:
                previous = next(i for i, p in enumerate(profiles) if p["id"] == old["id"])
                self.profiles.blockSignals(True)
                self.profiles.setCurrentRow(previous)
                self.profiles.blockSignals(False)
                return
        if index < 0:
            self.editing_id = None
            self.edit_rules = []
            self.render_rules()
            self.profile_name.clear()
            self.wallpaper_path.clear()
            self.voice_dir.clear()
            self.bgm_dir.clear()
            self.asset_dir.clear()
            self.accepted_dialogue_file=""
            self.dialogue_file.clear()
            self.load_shared_dialogue_library()
            return
        p = self.store.config["profiles"][index]
        from .assets import load_dialogues
        try:
            p["dialogues"] = load_dialogues(p)
        except (ValueError, OSError) as exc:
            self.report_error(tr('ui.8cc3752a3dfb', '读取台词库失败，保留配置中的原文本：') + str(exc))
        self.editing_id = p["id"]
        self.edit_private_root = p.get("private_asset_dir", "")
        for widget, key in [(self.profile_name, "name"), (self.wallpaper_path, "wallpaper"), (self.voice_dir, "voice_dir"), (self.bgm_dir, "bgm_dir")]:
            widget.setText(p[key])
        self.asset_dir.setText(p.get("asset_dir", ""))
        self.accepted_dialogue_file=p.get("dialogue_file", "")
        self.dialogue_file.setText(self.accepted_dialogue_file)
        self.original_audio_policy.setCurrentIndex(max(0, self.original_audio_policy.findData(p.get("original_audio_policy", "safe"))))
        self.original_audio_override.setCurrentIndex(max(0, self.original_audio_override.findData(p.get("original_audio_override", "auto"))))
        for widget, key in [(self.profile_enabled, "enabled"), (self.desktop_only, "desktop_only"),
                            (self.fullscreen_mute, "fullscreen_mute"), (self.bgm_enabled, "bgm_enabled"), (self.shuffle, "bgm_shuffle"), (self.bundled_demo_enabled,"use_bundled_demo")]:
            widget.blockSignals(True)
            widget.setChecked(p.get(key, True))
            widget.blockSignals(False)
        for widget, key in [(self.voice_volume, "voice_volume"), (self.bgm_volume, "bgm_volume"),
                            (self.duck, "duck_percent"), (self.global_cooldown, "global_cooldown")]:
            widget.blockSignals(True)
            widget.setValue(p[key])
            widget.blockSignals(False)
        self.demo_language.setCurrentIndex(max(0,self.demo_language.findData(p.get("demo_language","zh-CN"))))
        self.edit_rules = copy.deepcopy(p["rules"])
        self.edit_dialogues = copy.deepcopy(p.get("dialogues", []))
        self.render_dialogues()
        self.render_rules()
        if not self.tts_output.text() or self.tts_output.text() == old_voice_dir:
            self.tts_output.setText(p["voice_dir"])
        if self.is_standalone():
            self.select_standalone_profile(p["id"])
        elif self.manual.isChecked() and self.store.config["manual_profile"] != p["id"]:
            self.set_manual(True)

    def draft_profile(self):
        p = copy.deepcopy(self.store.profile(self.editing_id))
        if not p:
            raise ValueError(tr('ui.d74d6dbb1912', '请先绑定当前壁纸或新建配置'))
        p.update(name=self.profile_name.text().strip() or tr('ui.0d0bbabe5350', '壁纸配置'), wallpaper=self.wallpaper_path.text(),
                 voice_dir=self.voice_dir.text().strip(), bgm_dir=self.bgm_dir.text().strip(),
                 asset_dir=self.asset_dir.text().strip(), private_asset_dir=self.edit_private_root, dialogue_file=getattr(self,"accepted_dialogue_file",self.dialogue_file.text().strip()),
                 original_audio_policy=self.original_audio_policy.currentData(), original_audio_override=self.original_audio_override.currentData(),
                 enabled=self.profile_enabled.isChecked(), desktop_only=self.desktop_only.isChecked(),
                 fullscreen_mute=self.fullscreen_mute.isChecked(), bgm_enabled=self.bgm_enabled.isChecked(),
                 bgm_shuffle=self.shuffle.isChecked(), voice_volume=self.voice_volume.value(),
                 use_bundled_demo=self.bundled_demo_enabled.isChecked(), demo_language=self.demo_language.currentData(),
                 bgm_volume=self.bgm_volume.value(), duck_percent=self.duck.value(), global_cooldown=self.global_cooldown.value(),
                 rules=copy.deepcopy(self.edit_rules), dialogues=self.collect_dialogues())
        return p

    def save_profile(self):
        if self.dialogue_file.text().strip()!=getattr(self,"accepted_dialogue_file",""):
            return self.change_dialogue_file()
        before = copy.deepcopy(self.store.config)
        files = {}
        try:
            from .dialogues import normalize_dialogues
            p = self.draft_profile()
            p["dialogues"] = normalize_dialogues(p["dialogues"])
            for key in ["voice_dir", "bgm_dir"]:
                if p[key] and not Path(p[key]).is_dir():
                    raise ValueError(tr('ui.e027f7ba0479', '目录不存在，请先创建或选择已有文件夹：') + p[key])
            if p.get("dialogue_file"):
                from .assets import write_dialogues
                target = writable_path(p["dialogue_file"], self.store.protected())
                files[target] = target.read_bytes() if target.exists() else None
                write_dialogues(p["dialogue_file"], p["dialogues"], self.store.protected())
                for other in self.store.config["profiles"]:
                    if other["id"] != p["id"] and identity(other.get("dialogue_file", "")) == identity(p["dialogue_file"]):
                        other["dialogues"] = copy.deepcopy(p["dialogues"])
            index = next(i for i, q in enumerate(self.store.config["profiles"]) if q["id"] == p["id"])
            self.store.config["profiles"][index] = p
            self.store.save()
            self.refresh_profiles(p["id"])
            self.apply_saved_playback(before)
            self.log(tr('ui.7a637979d125', '已保存配置：') + p["name"])
            self.render_library()
            return True
        except Exception as exc:
            self.store.config = before
            from .autosave import Autosave
            try:
                Autosave.restore_files(files)
            except OSError as rollback:
                self.log(tr('ui.2bf1032a23e4', '台词保存回退失败：') + str(rollback))
            self.report_error(str(exc))
            return False

    def apply_saved_playback(self, before):
        """Apply edits without restarting an unrelated/current song or rule clocks."""
        current = self.store.profile(self.active_id)
        old = next((p for p in before.get("profiles", []) if p["id"] == self.active_id), None)
        if not current or not old or not hasattr(self.audio, "sync_bgm"):
            self.activate_profile(force=True)
            return
        if current.get("bgm_dir") != old.get("bgm_dir"):
            self.audio.set_profile(current)
        else:
            self.audio.profile = current
            self.audio.bgm_paused = bool(current.get("bgm_paused", False))
            self.audio.set_volumes()
            self.audio.sync_bgm()
        old_rules = {r["id"]: r for r in old["rules"]}
        new_rules = {r["id"]: r for r in current["rules"]}
        changed = {key for key in old_rules.keys() | new_rules.keys() if old_rules.get(key) != new_rules.get(key)}
        for key in changed:
            self.engine.last.pop(key, None); self.engine.next_due.pop(key, None); self.engine.daily_fired.pop(key, None)
        if changed or current.get("enabled") != old.get("enabled"):
            self.hooks.configure(current["rules"] if current.get("enabled", True) else [])
        self.apply_original_audio_policy()
        self.refresh_status()

    def add_profile(self):
        if hasattr(self, "autosave") and not self.autosave.flush():
            return
        from .assets import attach_resources, shared_root
        try:
            p = attach_resources(new_profile(), shared_root(self.store), self.store.protected())
        except Exception as exc:
            self.report_error(str(exc))
            return
        self.store.config["profiles"].append(p)
        self.store.save()
        self.refresh_profiles(p["id"])

    def bind_current(self):
        if hasattr(self, "autosave") and not self.autosave.flush():
            return
        if not self.current["path"]:
            QMessageBox.information(self, tr('ui.42f8118ce145', '尚无当前壁纸'), tr('ui.681484934e3d', '请先在 Wallpaper Engine 中播放一张壁纸，再点击立即检测。也可以先新建配置并开启手动模式测试。'))
            return
        p = self.store.bound_profile(self.current["path"])
        if p:
            self.refresh_profiles(p["id"])
            self.tabs.setCurrentIndex(0)
            return
        from .assets import attach_resources, shared_root
        try:
            p = attach_resources(new_profile(self.current["title"], self.current["path"]), shared_root(self.store), self.store.protected())
        except Exception as exc:
            self.report_error(str(exc))
            return
        self.store.config["profiles"].append(p)
        self.store.save()
        self.refresh_profiles(p["id"])
        self.tabs.setCurrentIndex(0)

    def rebind_current(self):
        if not self.editing_id or not self.current["path"]:
            QMessageBox.information(self, tr('ui.b2077d446fc8', '无法绑定'), tr('ui.fd6e74e4a777', '请选中配置，并确保 Wallpaper Engine 正在播放壁纸且已检测成功。'))
            return
        existing = self.store.bound_profile(self.current["path"])
        if existing and existing["id"] != self.editing_id:
            QMessageBox.information(self, tr('ui.e082fc3a5d7e', '此壁纸已有配置'), tr('ui.5ba175f10911', '请直接选择已有配置：') + existing["name"])
            return
        self.wallpaper_path.setText(self.current["path"])
        self.save_profile()

    def delete_profile(self):
        ids = [item.data(Qt.ItemDataRole.UserRole) for item in self.profiles.selectedItems()]
        if not ids and self.editing_id:
            ids = [self.editing_id]
        self.delete_profile_ids(ids)

    def delete_profile_ids(self, ids):
        ids = [identifier for identifier in set(ids) if self.store.profile(identifier)]
        if not ids:
            return
        if QMessageBox.question(self, tr('ui.6bbcbe49dc3f', '批量删除配置'), tr('ui.c5d912a6877c', '删除选中的 {value0} 个壁纸绑定配置？\n壁纸、语音、BGM 和共享台词文件全部保留。', value0=len(ids))) != QMessageBox.StandardButton.Yes:
            return
        try:
            if self.editing_id and self.editing_id not in ids and self.draft_profile() != self.store.profile(self.editing_id):
                if not self.save_profile():
                    return
            from .library import remove_profiles
            count = remove_profiles(self.store, ids)
            if self.editing_id in ids:
                self.editing_id = None
            self.refresh_profiles()
            self.render_library()
            self.activate_profile(force=True)
            self.log(tr('ui.b9b64e6c82f7', '已删除 {value0} 个绑定，资源文件保留。', value0=count))
        except Exception as exc:
            self.report_error(str(exc))

    def make_audio_dirs(self):
        self.configure_resources(dedicated=True)

    def configure_resources(self, dedicated=False):
        if not self.editing_id:
            self.report_error(tr('ui.c612fc7a29a2', '请先新建或绑定配置'))
            return
        try:
            from .resources_ui import ResourceDialog
            dialog = ResourceDialog(self.store, self.draft_profile(), self, dedicated)
            if dialog.exec():
                if dedicated and QMessageBox.question(
                    self, tr('ui.2f1ff27b77e5', '确认建立专用音频目录'), dialog.confirmation_text(),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                ) != QMessageBox.StandardButton.Yes:
                    return
                self.apply_resource_profile(dialog.apply())
        except Exception as exc:
            self.report_error(str(exc))

    def use_asset_directory(self):
        try:
            from .assets import attach_resources
            from .assets import shared_root
            attached = attach_resources(self.draft_profile(), self.asset_dir.text().strip() or shared_root(self.store), self.store.protected())
            self.apply_resource_profile(attached)
        except Exception as exc:
            self.report_error(str(exc))

    def apply_resource_profile(self, attached):
        self.edit_private_root = attached.get("private_asset_dir", "")
        for widget, key in [(self.asset_dir, "asset_dir"), (self.voice_dir, "voice_dir"), (self.bgm_dir, "bgm_dir"), (self.dialogue_file, "dialogue_file")]:
            widget.setText(attached[key])
        self.accepted_dialogue_file=self.dialogue_file.text()
        self.edit_dialogues = attached["dialogues"]
        self.render_dialogues()
        if self.save_profile():
            self.tts_output.setText(self.voice_dir.text())
            return True
        return False

    def live_bgm_volume(self, value):
        if self.editing_id != self.active_id or not self.active_id:
            return
        profile = self.store.profile(self.active_id)
        if profile:
            profile["bgm_volume"] = value
            self.audio.set_volumes()
            try:
                self.store.save()
            except Exception as exc:
                self.log(tr('ui.3975a9ba83a8', '保存实时 BGM 音量失败：') + str(exc))

    def toggle_bgm(self):
        profile = self.store.profile(self.active_id)
        if not profile:
            self.log(tr('ui.edb24332a56a', '当前没有播放配置，无法切换 BGM。'))
            return
        try:
            paused = not bool(getattr(self.audio, "bgm_paused", False))
            profile["bgm_paused"] = paused
            self.store.save()
            self.audio.set_bgm_paused(paused)
            self.refresh_status()
        except Exception as exc:
            self.report_error(str(exc))

    def probe_original_audio(self):
        self.original_audio_request += 1
        token = self.original_audio_request
        if self.is_standalone():
            self.original_audio=dict(state="no",detail=tr("mode.no_detection","独立模式不检测原壁纸声音。"))
            self.apply_original_audio_policy();return
        profile = self.store.profile(self.active_id)
        self.original_audio = dict(state="unknown", detail=tr('ui.e8b970bc3e05', '正在检测…') if profile else tr('ui.c4fecacc70a6', '当前无播放配置'))
        self.apply_original_audio_policy()
        if not profile:
            return
        detector = self.registry.audio_detectors[self.store.config.get("audio_detector", "builtin")][1]
        config, wallpaper = copy.deepcopy(self.store.config), profile.get("wallpaper", "")
        def done(result):
            if token == self.original_audio_request:
                self.original_audio = result
                self.apply_original_audio_policy()
        def failed(error):
            done(dict(state="unknown", detail=tr('ui.f7293a061e9a', '检测失败：') + str(error)))
        self.submit(lambda: detector(config, wallpaper), done, failed)

    def apply_original_audio_policy(self):
        from .original_audio import should_block_bgm
        profile = self.store.profile(self.active_id)
        blocked = bool(not self.is_standalone() and profile and should_block_bgm(profile, self.original_audio))
        if hasattr(self.audio, "set_bgm_blocked"):
            self.audio.set_bgm_blocked(blocked)
        self.original_audio_label.setText(self.original_audio["detail"] + (tr('ui.7373ed1d1ab4', '；防冲突暂停伴随 BGM') if blocked else ""))
        self.refresh_status()

    def refresh_startup_button(self, enabled):
        self.startup_button.setText(tr('ui.e63351444294', '开机自启：已开启（点击关闭）') if enabled else tr('ui.6879d4d925b0', '开机自启：已关闭（点击开启）'))

    def toggle_startup(self):
        from .startup import startup_enabled, set_startup
        try:
            enabled = not startup_enabled()
            set_startup(enabled)
            self.refresh_startup_button(enabled)
            self.log(tr('ui.5b5912138fcb', '已开启当前用户登录自启，登录后留在托盘。') if enabled else tr('ui.0bd50d3402da', '已关闭开机自启。'))
        except Exception as exc:
            self.report_error(str(exc))

    def toggle_hover_help(self):
        enabled = not self.hover_help.enabled
        self.hover_help.set_enabled(enabled)
        self.store.config["hover_help"] = enabled
        self.help_button.setText(tr('ui.4d9a0c931f4b', '悬停说明：开启') if enabled else tr('ui.f0eddb923dcd', '悬停说明：关闭'))
        try:
            self.store.save()
        except Exception as exc:
            self.report_error(str(exc))

    def open_document(self, name):
        from .documents_ui import DocumentViewer
        try:
            if not getattr(self, "document_viewer", None):
                self.document_viewer = DocumentViewer(ROOT, self)
            self.document_viewer.load_document(ROOT / name)
            self.document_viewer.show()
            self.document_viewer.raise_()
            self.document_viewer.activateWindow()
            return True
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr('ui.8c0c99b071d5', '无法打开说明'), tr('ui.c94538d0355a', '请检查程序目录内的说明文件是否完整。\n') + str(exc))
            return False

    def open_folder(self, path):
        if not path or not Path(path).is_dir():
            QMessageBox.information(self, tr('ui.85c016964ce0', '目录不存在'), tr('ui.cf382bd48a4c', '请先选择或建立有效目录。'))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    def render_rules(self):
        self.rules_table.setRowCount(len(self.edit_rules))
        for i, r in enumerate(self.edit_rules):
            trigger = EVENTS.get(r["event"], r["event"])
            if r["event"] == "key":
                from .rules import display_hotkey
                trigger += " " + display_hotkey(r["hotkey"])
            elif r["event"] == "scheduled":
                trigger += " " + r.get("at", "09:00")
            window = tr('ui.0b97c851e4a7', '全天') if r["start"] == r["end"] else r["start"] + "–" + r["end"]
            source = r["source"] or tr('ui.01ffb0c854fe', '语音总目录')
            if r["keyword"]:
                source += " / " + r["keyword"]
            for j, text in enumerate(["✓" if r["enabled"] else "—", r["name"], trigger, window, source]):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.rules_table.setItem(i, j, item)

    def add_rule(self):
        dialog = RuleDialog(parent=self, existing_rules=self.edit_rules)
        if dialog.exec():
            self.edit_rules.append(dialog.rule)
            self.render_rules()

    def edit_rule(self):
        i = self.rules_table.currentRow()
        if i >= 0:
            dialog = RuleDialog(self.edit_rules[i], self, existing_rules=self.edit_rules)
            if dialog.exec():
                self.edit_rules[i] = dialog.rule
                self.render_rules()

    def delete_rule(self):
        i = self.rules_table.currentRow()
        if i >= 0:
            self.edit_rules.pop(i)
            self.render_rules()

    def export_interaction_preset(self):
        from .presets import write_preset
        from .assets import load_dialogues
        ids = [item.data(Qt.ItemDataRole.UserRole) for item in self.profiles.selectedItems()]
        profiles = []
        for identifier in ids or ([self.editing_id] if self.editing_id else []):
            profile = self.draft_profile() if identifier == self.editing_id else copy.deepcopy(self.store.profile(identifier))
            if profile:
                if identifier != self.editing_id:
                    profile["dialogues"] = load_dialogues(profile)
                profiles.append(profile)
        if not profiles:
            self.report_error(tr('ui.63016cd4660c', '请先选择要导出的配置'))
            return
        path, _ = QFileDialog.getSaveFileName(self, tr('ui.18d3a0f6e001', '导出可分享互动配置'), "interaction-preset.json", tr('ui.a0b0dbc047aa', '互动配置 (*.json)'))
        if path:
            try:
                warnings = write_preset(path, profiles, self.store.protected())
                self.log(tr('ui.cecbff102a40', '已导出 {value0} 个互动配置，不包含音频和密钥：{value1}', value0=len(profiles), value1=path))
                if warnings:
                    QMessageBox.information(self, tr('ui.643c6c463b2e', '导出完成，请核对音频来源'), "\n".join(warnings))
            except Exception as exc:
                self.report_error(str(exc))

    def import_interaction_preset(self):
        from .presets import read_preset, validate_payload
        from .presets_ui import PresetImportDialog
        path, _ = QFileDialog.getOpenFileName(self, tr('ui.56bc118ba419', '导入可分享互动配置'), "", tr('ui.a0b0dbc047aa', '互动配置 (*.json)'))
        if not path:
            return
        try:
            payload = read_preset(path)
            profiles, warnings = validate_payload(payload, self.registry.events)
            target = self.store.profile(self.editing_id)
            dialog = PresetImportDialog(profiles, warnings, target, self)
            if dialog.exec():
                self.apply_interaction_preset(payload, target["id"] if target and dialog.mode.currentData() == "replace" else None)
        except Exception as exc:
            self.report_error(str(exc))

    def apply_interaction_preset(self, payload, target_id=None):
        from .presets import import_payload
        if self.editing_id and self.draft_profile() != self.store.profile(self.editing_id):
            if not self.save_profile():
                return
        result = import_payload(self.store, payload, target_id, self.registry.events)
        self.refresh_profiles(result["profile_ids"][0])
        self.render_library()
        self.activate_profile(force=True)
        self.log(tr('ui.13063b7dc11a', '已导入 {value0} 个配置。请核对本机语音目录并绑定壁纸。', value0=len(result['profile_ids'])))
        for warning in result["warnings"]:
            self.log(warning)
        return result

    def preview_rule(self):
        i = self.rules_table.currentRow()
        if i < 0:
            return
        try:
            files = candidates(self.draft_profile(), self.edit_rules[i])
            self.preview(files)
        except Exception as exc:
            self.report_error(str(exc))

    def preview_voice(self):
        self.preview(candidates(self.draft_profile(),dict(source="",keyword="")) if self.editing_id else audio_files(self.voice_dir.text()))

    def preview(self, files):
        if not files:
            QMessageBox.information(self, tr('ui.26cd8aaaafca', '未找到语音'), tr('ui.b2b35c8f98f0', '目录里没有匹配的音频。请放入文件、检查规则筛选，或先到“生成语音”生成台词。'))
            return
        self.audio.voice_output.setVolume(self.voice_volume.value() / 100)
        self.audio.play_voice(random.choice(files))

    def set_manual(self, enabled):
        if self.is_standalone():return
        self.store.config["manual_profile"] = (self.editing_id or "") if enabled else ""
        self.store.save()
        self.activate_profile(force=True)

    def detect(self, command=False):
        if self.is_standalone():return
        if self.query_busy:
            return
        self.query_busy = True
        backend = self.store.config.get("wallpaper_backend", "wallpaper_engine")
        query = self.registry.wallpapers[backend][1]
        config = copy.deepcopy(self.store.config)
        if backend == "wallpaper_engine":
            config["_wallpaper_command_query"] = bool(command)
        epoch=self.mode_epoch
        self.submit(lambda: query(config), lambda result:self.detected(result) if epoch==self.mode_epoch else None,lambda error:self.detect_error(error) if epoch==self.mode_epoch else None)

    def detected(self, result, epoch=None):
        if self.is_standalone() or epoch is not None and epoch!=self.mode_epoch:return
        self.query_busy = False
        self.current = result
        self.current_display_text = tr('ui.8fb967b32937', '当前壁纸  ·  ') + result["title"] + (tr('ui.2b57d457af7e', '\n识别来源：') + result["source"] if result.get("source", "") != tr('ui.0cb15544cc0d', '官方查询') and result.get("source") else "")
        if not self.store.config.get("we_dir") and not result.get("running"):
            self.current_display_text=tr("mode.recommend","未发现 WE 安装目录，推荐选择独立声音伴随；不需要安装 WE。")
        self.current_display_tooltip = result["path"]
        self.render_current_wallpaper()
        self.activate_profile()

    def detect_error(self, error, epoch=None):
        if self.is_standalone() or epoch is not None and epoch!=self.mode_epoch:return
        self.query_busy = False
        self.current = dict(path="", title=tr('ui.78fc411a3ba9', '检测失败'), running=False)
        self.current_display_text = tr('ui.65bceeb27a23', '检测失败  ·  ') + str(error)
        self.current_display_tooltip = ""
        self.render_current_wallpaper()
        if getattr(self, "last_detect_error", "") != str(error):
            self.log(tr('ui.64fbec13d6c7', '壁纸检测失败：') + str(error))
        self.last_detect_error = str(error)
        self.activate_profile()

    def activate_profile(self, force=False):
        manual = self.store.config.get("standalone_profile","") if self.is_standalone() else self.store.config["manual_profile"]
        p = self.store.profile(manual) if manual else self.store.bound_profile(self.current["path"])
        next_id = p["id"] if p else None
        if force or next_id != self.active_id:
            self.active_id = next_id
            self.engine.reset()
            if hasattr(self.audio, "set_bgm_blocked"):
                self.audio.set_bgm_blocked(True)
            self.audio.set_profile(p)
            self.probe_original_audio()
            try:
                self.hooks.configure(p["rules"] if p and p.get("enabled", True) else [])
            except Exception as exc:
                self.log(tr('ui.c81035eefbc5', '快捷键配置失败：') + str(exc))
            if p:
                self.log(tr('ui.dfb802238b38', '已启用') + (tr('ui.6468f7ce3544', '手动配置：') if manual else tr('ui.c02269d462ef', '壁纸配置：')) + p["name"])
                if not force:
                    self.input_event("startup", "")
        self.refresh_status()

    def refresh_status(self):
        if not self.isVisible():
            return
        p = self.store.profile(self.active_id)
        if self.paused:
            text = tr('ui.5649520b64d2', '已暂停伴随声音和触发')
        elif self.fullscreen:
            text = tr('ui.f991996e6891', '全屏应用中 · 伴随声音已暂停')
        elif not p:
            text = tr('ui.9946c2b50ac3', '等待绑定当前壁纸，或开启手动配置')
        elif not p.get("enabled", True):
            text = tr('ui.c8359eede454', '当前配置已停用：') + p["name"]
        else:
            text = (tr("mode.standalone","独立声音伴随") if self.is_standalone() else tr('ui.0b19f458b183', '手动模式') if self.store.config["manual_profile"] else tr('ui.7019c7b4387d', '自动跟随')) + "  ·  " + p["name"]
            if self.audio.last_bgm:
                text += "  ·  BGM：" + self.audio.last_bgm.name
            if getattr(self.audio, "bgm_paused", False):
                text += tr('ui.88a48f2a71f2', '  ·  BGM 已手动暂停')
            elif getattr(self.audio, "bgm_blocked", False):
                text += tr('ui.912172130ce9', '  ·  BGM 防冲突暂停')
        if self.status_label.text() != text:
            self.status_label.setText(text)
        title = tr('ui.f122ce30f121', '继续当前 BGM') if getattr(self.audio, "bgm_paused", False) else tr('ui.f6a654e97a81', '暂停当前 BGM')
        if self.bgm_pause_button.text() != title:
            self.bgm_pause_button.setText(title)
        self.refresh_shell()

    def render_current_wallpaper(self):
        if not self.isVisible():
            return
        if self.current_label.text() != self.current_display_text:
            self.current_label.setText(self.current_display_text)
        if self.current_label.toolTip() != self.current_display_tooltip:
            self.current_label.setToolTip(self.current_display_tooltip)

    def showEvent(self, event):
        super().showEvent(event)
        self.render_current_wallpaper()
        self.refresh_status()

    def toggle_pause(self):
        self.paused = not self.paused
        title = tr('ui.9f7a28a515d1', '继续伴随') if self.paused else tr('ui.a555aecaab24', '暂停伴随')
        self.pause_button.setText(title)
        self.tray_pause.setText(title)
        self.audio.set_paused(self.paused or self.fullscreen)
        self.refresh_status()

    def input_event(self, event, hotkey):
        p = self.store.profile(self.active_id)
        if not p or self.paused or self.fullscreen or self.audio.busy:
            return
        state = foreground_state()
        automatic = event in {"random", "scheduled", "startup"} or bool(self.registry.events.get(event, (None, None))[1])
        if not automatic:
            if state["own"] or (p.get("desktop_only", True) and not state["desktop"]):
                return
        if p.get("fullscreen_mute", True) and state["fullscreen"]:
            return
        chosen = self.engine.choose(p, event, hotkey=hotkey)
        if chosen:
            rule, path = chosen
            self.log(tr('ui.0ea8aca65cd3', '触发：') + rule["name"])
            self.audio.play_voice(path)

    def on_tick(self):
        p = self.store.profile(self.active_id)
        full = bool(p and p.get("fullscreen_mute", True) and foreground_state()["fullscreen"])
        if full != self.fullscreen:
            self.fullscreen = full
            self.refresh_status()
        self.audio.set_paused(self.paused or full)
        self.input_event("scheduled", "")
        self.input_event("random", "")
        for event, (_, poll) in self.registry.events.items():
            if poll:
                try:
                    if poll(self.store.config, datetime.now()):
                        self.input_event(event, "")
                except Exception as exc:
                    if getattr(self, "last_extension_error", "") != str(exc):
                        self.log(tr('ui.ed3729cc79e4', '扩展事件错误：') + str(exc))
                    self.last_extension_error = str(exc)

    def refresh_language_notice(self):
        pending = self.ui_language.currentData() != language()
        self.language_notice.setText(tr("settings.language_next_start", "界面语言将在下次启动时生效。") if pending else "")
        self.language_notice.setVisible(pending)

    def load_settings(self):
        c = self.store.config
        self.run_mode.blockSignals(True);self.run_mode.setCurrentIndex(max(0,self.run_mode.findData(c.get("run_mode","wallpaper_engine"))));self.run_mode.blockSignals(False)
        self.apply_run_mode()
        self.ui_language.setCurrentIndex(max(0, self.ui_language.findData(c.get("ui_language", "zh-CN"))))
        self.refresh_language_notice()
        self.we_dir.setText(c["we_dir"])
        self.workshop_dir.setText(c["workshop_dir"])
        self.monitor.setValue(c["monitor"])
        self.poll_seconds.setValue(c["poll_seconds"])
        self.operation_voice_enabled.blockSignals(True)
        self.operation_voice_enabled.setChecked(c.get("operation_voice_enabled", True))
        self.operation_voice_enabled.blockSignals(False)
        self.operation_voice_dir.setText(c.get("operation_voice_dir", ""))
        self.ffprobe_path.setText(c.get("ffprobe", ""))
        for i in range(self.plugin_list.count()):
            item = self.plugin_list.item(i)
            item.setCheckState(Qt.CheckState.Checked if item.text() in c.get("enabled_plugins", []) else Qt.CheckState.Unchecked)
        for setting, combo in self.backend_combos.items():
            combo.setCurrentIndex(max(0, combo.findData(c.get(setting))))

    def save_settings(self):
        before = copy.deepcopy(self.store.config)
        try:
            self.store.config.update(ui_language=self.ui_language.currentData(), we_dir=self.we_dir.text().strip(), workshop_dir=self.workshop_dir.text().strip(),
                                     monitor=self.monitor.value(), poll_seconds=self.poll_seconds.value(), ffprobe=self.ffprobe_path.text().strip(),
                                     operation_voice_enabled=self.operation_voice_enabled.isChecked(), operation_voice_dir=self.operation_voice_dir.text().strip())
            for setting, combo in self.backend_combos.items():
                self.store.config[setting] = combo.currentData()
            self.store.config["enabled_plugins"] = [self.plugin_list.item(i).text() for i in range(self.plugin_list.count())
                                                    if self.plugin_list.item(i).checkState() == Qt.CheckState.Checked]
            self.store.save()
            self.poll.setInterval(self.poll_seconds.value() * 1000)
            self.log(tr('ui.787c5a4f0b63', '运行设置已保存；扩展和播放/输入后端变更重启后生效'))
            if before.get("ui_language", "zh-CN") != self.store.config["ui_language"]:
                self.autosave.show(tr("settings.language_next_start", "界面语言将在下次启动时生效。"))
            self.detect()
            self.probe_original_audio()
            if hasattr(self, "autosave"):
                self.autosave.remember("runtime")
            if hasattr(self, "operation_voices"):
                self.operation_voices.refresh()
            return True
        except Exception as exc:
            self.store.config = before
            self.report_error(str(exc))
            return False

    def restore_defaults(self):
        if not self.autosave.flush():
            return
        if QMessageBox.question(self, tr('ui.4cfa493e0ec9', '恢复默认配置'), tr('ui.82238f40a9f7', '恢复运行偏好、外观，以及当前壁纸的音量、播放开关和互动规则？\n壁纸绑定、资源路径、台词、音频、角色模型及接口设置全部保留；不开关系统自启。可撤销。'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        before = copy.deepcopy(self.store.config)
        try:
            from .core import defaults
            c = defaults()
            for key in ("ui_language", "monitor", "poll_seconds", "hover_help", "appearance", "operation_voice_enabled", "operation_voice_rules", "operation_voice_min_interval", "enabled_plugins", *self.backend_combos):
                self.store.config[key] = copy.deepcopy(c[key])
            p = self.store.profile(self.editing_id)
            if p:
                fresh = new_profile()
                for key in ("enabled", "bgm_enabled", "bgm_shuffle", "bgm_paused", "desktop_only", "fullscreen_mute",
                            "voice_volume", "bgm_volume", "duck_percent", "global_cooldown", "rules"):
                    p[key] = copy.deepcopy(fresh[key])
            self.store.save()
            self.autosave.busy = True
            self.refresh_profiles(self.editing_id); self.load_settings()
            self.apply_appearance()
            self.hover_help.set_enabled(True); self.help_button.setText(tr('ui.4d9a0c931f4b', '悬停说明：开启'))
            self.poll.setInterval(self.poll_seconds.value() * 1000)
            self.activate_profile(force=True)
            self.autosave.baseline = self.autosave.forms()
            self.autosave.record(before, {}, tr('ui.6cf9655ecf12', '已恢复默认配置，个人资源保留；可撤销。'))
        except Exception as exc:
            self.store.config = before
            self.report_error(tr('ui.46cc8b21a96b', '恢复默认失败：') + str(exc))
        finally:
            self.autosave.busy = False

    def toggle_operation_voice(self, enabled):
        if not hasattr(self, "autosave"):
            return
        if not self.autosave.flush():
            self.operation_voice_enabled.blockSignals(True)
            self.operation_voice_enabled.setChecked(self.store.config.get("operation_voice_enabled", True))
            self.operation_voice_enabled.blockSignals(False)
            return
        if not enabled and hasattr(self, "operation_voices"):
            self.operation_voices.change_timer.stop()
            source = self.audio.voice.source().toLocalFile()
            if source and identity(source) == identity(self.operation_voices.source):
                self.audio.voice.stop()
        self.log(tr('ui.3164cdc327ac', '操作回应语音已开启。') if enabled else tr('ui.55e7ded361dc', '操作回应语音已关闭。'))

    def configure_operation_rules(self):
        if not self.autosave.flush():
            return
        from .operation_rules_ui import OperationRulesDialog
        dialog = OperationRulesDialog(self)
        if dialog.exec():
            self.apply_operation_rules(dialog.result_payload)

    def apply_operation_rules(self, payload):
        from .operation_rules import normalize_payload
        before = copy.deepcopy(self.store.config)
        try:
            value = normalize_payload(payload)
            self.store.config.update(operation_voice_enabled=value["enabled"],operation_voice_rules=value["rules"],operation_voice_min_interval=value["min_interval"])
            self.store.save()
            self.operation_voice_enabled.blockSignals(True)
            self.operation_voice_enabled.setChecked(value["enabled"])
            self.operation_voice_enabled.blockSignals(False)
            self.autosave.remember("runtime")
            self.operation_voices.refresh()
            self.autosave.record(before, {}, tr('ui.3719e07f7a03', '操作回应规则已保存，独立于壁纸规则；可撤销。'))
            return True
        except Exception as exc:
            self.store.config = before
            self.report_error(tr('ui.87f14b33ed94', '操作回应规则保存失败：') + str(exc))
            return False

    def load_tts(self):
        self.filename_model.setText(self.store.config.get("tts_filename_model", ""))
        self.rendered_provider = ""  # Restoring saved settings must not stash the stale form over them.
        self.provider_cache = copy.deepcopy(self.store.config.get("tts_providers", {}))
        self.provider_cache.setdefault("gpt_sovits", self.store.config["tts"])
        index = self.provider_choice.findData(self.store.config.get("tts_provider", "gpt_sovits"))
        self.provider_choice.blockSignals(True)
        self.provider_choice.setCurrentIndex(max(0, index))
        self.provider_choice.blockSignals(False)
        self.switch_provider()

    def tts_settings(self):
        self.stash_provider()
        return copy.deepcopy(self.provider_cache[self.provider_choice.currentData()])

    def generation_settings(self):
        from .audio_names import infer_model_label
        settings = self.tts_settings()
        identifier = self.character_choice.currentData() if self.provider_choice.currentData()=="gpt_sovits" else None
        character = next((e for e in self.store.config.get("tts_characters",[]) if e["id"]==identifier),None)
        label = self.filename_model.text().strip() or infer_model_label(settings,self.provider_choice.currentData(),character)
        return {**settings,"_filename_model":label}

    def save_tts(self):
        self.stash_provider()
        before = copy.deepcopy(self.store.config)
        try:
            sanitized = copy.deepcopy(self.provider_cache)
            from .secrets import write_secret
            for identifier, values in sanitized.items():
                provider = self.registry.speech.get(identifier)
                secret_keys = {field.key for field in provider.fields if field.kind == "password"} if provider else set()
                secret_keys.add("api_key")
                for secret_key in secret_keys:
                    if secret_key in values:
                        account = identifier if secret_key == "api_key" else identifier + ":" + secret_key
                        write_secret(account, values.pop(secret_key))
            self.store.config["tts_provider"] = self.provider_choice.currentData()
            self.store.config["tts_filename_model"] = self.filename_model.text().strip()
            self.store.config["tts_providers"] = sanitized
            self.store.config["tts"] = sanitized.get("gpt_sovits", self.store.config["tts"])
            if self.provider_choice.currentData() == "gpt_sovits":
                self.store.config["tts_character"] = self.character_choice.currentData() or ""
            self.store.save()
            self.api_message(tr('ui.2a9475105007', '语音接口设置已保存。保存设置不会启动 API 或生成音频。'))
            if hasattr(self, "autosave"):
                self.autosave.remember("tts")
            return True
        except Exception as exc:
            self.store.config = before
            self.report_error(str(exc))
            return False

    def use_voice_dir(self):
        from .assets import shared_root
        value = self.voice_dir.text().strip() if self.editing_id else str(shared_root(self.store) / "voice")
        if not value:
            self.api_message(tr('ui.ee233edf5c32', '当前配置尚未设置语音目录，请先在资源与绑定中选择。'))
            return
        self.tts_output.setText(value)
        self.api_message(tr('ui.5534905ab289', '生成保存目录已切换为：') + value)

    def preview_reference_audio(self):
        try:
            from .core import AUDIO_EXTENSIONS
            settings = self.tts_settings()
            value = str(settings.get("reference", "")).strip()
            path = Path(value)
            if value and self.provider_choice.currentData() == "gpt_sovits":
                from .characters import project_file
                path = project_file(settings, "reference")
            if not value or not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                raise ValueError(tr('ui.b6948b98b944', '请先选择有效的参考音频文件。试听不会启动 API。'))
            self.preview([path])
            self.api_message(tr('ui.7339e8341392', '正在试听参考音频：') + path.name)
        except Exception as exc:
            self.report_error(str(exc))

    def update_api_controls(self):
        from .managed_api import api
        local = self.provider_choice.currentData() == "gpt_sovits"
        self.api_close_mode = local and api.owns_service() is True
        self.start_api_button.setText(tr('ui.e0ec003b92ec', '关闭自建 API') if self.api_close_mode else tr('ui.44f396b9cc0c', '启动本地 API'))
        self.start_api_button.setToolTip(tr('ui.6995910656ba', '启动本机 API，或关闭本程序启动的 API 进程树。外部服务不会被关闭或切换；加载和生成期间不可操作。'))
        busy = self.api_busy or self.tts_busy
        self.start_api_button.setEnabled(not busy)
        self.check_api_button.setEnabled(not busy)
        self.provider_choice.setEnabled(not busy)
        self.generate_button.setEnabled(not busy)

    def check_api(self):
        if self.api_busy or self.tts_busy:
            self.api_message(tr('ui.df13d72d4ce9', '已有语音或接口任务正在进行，请等待完成。'))
            return
        settings = self.tts_settings()
        self.api_busy = True
        self.api_message(tr('ui.3a1b5e2ba8d2', '正在检测连接，检测不会自动启动 API…'))
        provider = self.registry.speech[self.provider_choice.currentData()]
        def check():
            import requests
            try:
                return provider.check(settings)
            except (requests.ConnectionError, requests.Timeout) as exc:
                if provider.id == "gpt_sovits":
                    raise ValueError(tr('ui.28a3e494e7e0', '本地 API 尚未启动或暂时无法连接。请点击“启动本地 API”，等待就绪后再检测；也可直接生成以自动启动。请同时核对地址和端口。')) from exc
                raise ValueError(tr('ui.e2f0b148f402', '接口连接失败，请检查服务地址与网络。')) from exc
        self.submit(check, self.api_finished, self.api_error)

    def launch_api(self):
        if self.api_busy or self.tts_busy:
            self.api_message(tr('ui.df13d72d4ce9', '已有语音或接口任务正在进行，请等待完成。'))
            return
        settings = self.tts_settings()
        provider = self.registry.speech[self.provider_choice.currentData()]
        if provider.id == "gpt_sovits":
            from .managed_api import api
            settings = {**settings, "_tts_status": self.api_stage.emit}
            # Honor the displayed action even if the process exited while idle.
            closing = self.api_close_mode
            self.api_busy = True
            self.api_message(tr('ui.5ef9453eef81', '正在关闭自建 API 并回收进程…') if closing else tr('ui.f75257b08330', '正在启动或连接本地 API、等待模型加载，请稍候…'))
            self.submit(api.close_owned if closing else lambda: api.start(settings, self.store.protected()), self.api_finished, self.api_error)
            return
        if provider.start:
            self.api_busy = True
            self.api_message(tr('ui.95c64f8662e8', '正在启动所选接口…'))
            self.submit(lambda: provider.start(settings, self.store.protected()), self.api_finished, self.api_error)

    def api_finished(self, message):
        self.api_busy = False
        self.api_message(message)

    def api_message(self, message):
        self.tts_status.setText(str(message))
        self.log(str(message))
        self.update_api_controls()

    def api_error(self, error):
        self.api_busy = False
        self.api_message(tr('ui.13a81a0a1f3a', '接口操作未完成：') + str(error))

    def generate_audio(self):
        if self.tts_busy or self.api_busy:
            self.api_message(tr('ui.df13d72d4ce9', '已有语音或接口任务正在进行，请等待完成。'))
            return
        lines = [line.strip() for line in self.lines.toPlainText().splitlines() if line.strip()]
        output = self.tts_output.text().strip()
        try:
            if not lines:
                raise ValueError(tr('ui.7910b9fff9b7', '请每行填写一条待生成台词'))
            if not output:
                raise ValueError(tr('ui.0f8d02a0647f', '请选择生成保存目录'))
            writable_path(output, self.store.protected())
            settings = self.generation_settings()
            if not self.save_tts():
                return
            provider = self.registry.speech[self.provider_choice.currentData()]
        except Exception as exc:
            self.report_error(str(exc))
            return
        entries = self.transferred_dialogues if self.lines.toPlainText() == self.transferred_lines else None
        self.begin_generation_review(lines, output, settings, provider, self.skip_existing_tts_audio.isChecked(), entries)

    def generated(self, paths):
        self.tts_busy = False
        if hasattr(self, "operation_voices"):
            self.operation_voices.refresh()
            self.operation_voices.request("complete")
        self.update_api_controls()
        self.generate_button.setEnabled(True)
        skipped = max(0, getattr(self, "pending_generation_total", len(paths)) - len(paths))
        self.tts_status.setText(tr('ui.08101138d44b', '已保存 {value0} 条语音，跳过 {value1} 条已有或重复音频。', value0=len(paths), value1=skipped))
        self.finish_generation_progress(True, self.tts_status.text())
        for path in paths:
            self.log(tr('ui.97f2f7671059', '已生成：') + path)

    def generation_error(self, error):
        self.tts_busy = False
        self.update_api_controls()
        self.generate_button.setEnabled(True)
        self.tts_status.setText(tr('ui.cc34de39da37', '生成未完成：') + str(error))
        self.finish_generation_progress(False, self.tts_status.text())
        self.report_error(str(error))

    def closeEvent(self, event):
        if not self.quitting and hasattr(self, "autosave") and not self.autosave.flush():
            event.ignore()
            return
        if self.quitting or not QSystemTrayIcon.isSystemTrayAvailable():
            event.accept()
            self.cleanup()
            QApplication.quit()
        else:
            event.ignore()
            self.hide()
            if not getattr(self, "tray_notice", False):
                self.tray.showMessage(tr('ui.e52fa9b152e1', '壁纸声伴'), tr('ui.30fc1fecaf42', '已在托盘继续运行；右键图标可暂停或退出。'))
                self.tray_notice = True

    def quit_app(self):
        if self.tts_busy:
            if QMessageBox.question(self, tr('ui.83ed743b5b1b', '退出并取消生成'), tr('ui.277994b82fa3', '退出将取消剩余生成并停止声伴启动的本地 API；已经保存的音频保留。继续退出？')) != QMessageBox.StandardButton.Yes:
                return
        if not self.autosave.flush():
            return
        self.cleanup()
        QApplication.quit()

    def cleanup(self):
        if self.quitting:
            return
        self.quitting = True
        self.autosave.close()
        self.operation_voices.close()
        self.character_scan_timer.stop()
        self.commit_player_volume()
        self.player_volume_timer.stop()
        self.generation_cancel.set()
        self.action_feedback.close()
        self.button_motion.close()
        from .managed_api import api
        try:
            api.shutdown()
        except Exception as exc:
            self.log(tr('ui.655dd40d7186', '停止自建 API 失败：') + str(exc))
        self.poll.stop()
        self.tick.stop()
        self.hooks.stop()
        self.audio.stop()
        self.tray.hide()
        self.executor.shutdown(wait=False, cancel_futures=True)
