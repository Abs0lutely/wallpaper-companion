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
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QStyle, QSystemTrayIcon, QTabWidget, QTableWidget,
    QTableWidgetItem, QTimeEdit, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView,
)

from .core import DATA, ROOT, PLUGIN_DIR, Store, RuleEngine, audio_files, candidates, identity, new_profile, new_rule, writable_path
from .audio import Audio
from .services import InputHooks, api_status, current_wallpaper, foreground_state, generate, start_api
from .extensions import load_extensions
from .library_ui import LibraryMixin, DialogueMixin

EVENTS = {
    "key": "快捷键", "mouse_left": "鼠标左键", "mouse_right": "鼠标右键", "mouse_middle": "鼠标中键",
    "mouse_x1": "鼠标侧键 X1", "mouse_x2": "鼠标侧键 X2", "scroll_up": "滚轮向上", "scroll_down": "滚轮向下",
    "any_key": "任意按键", "random": "定时随机", "startup": "绑定的壁纸开始播放",
    "scheduled": "每天固定时刻",
}

STYLE = """
QWidget { background:#111827; color:#e5eaf4; font-family:'Microsoft YaHei UI'; font-size:13px; }
QMainWindow, QDialog { background:#111827; }
QLabel#brand { font-size:25px; font-weight:700; color:#f8fafc; }
QLabel#subtle { color:#94a3b8; }
QLabel#current { background:#1c2940; border:1px solid #334966; border-radius:10px; padding:14px; font-size:15px; }
QLabel#status { color:#67e8c8; padding:6px; }
QPushButton { background:#24334b; border:1px solid #3c506c; border-radius:6px; padding:8px 13px; }
QPushButton:hover { background:#334966; }
QPushButton:disabled { color:#64748b; background:#1e293b; }
QPushButton#primary { background:#0f766e; border-color:#14b8a6; font-weight:600; }
QPushButton#primary:hover { background:#0d9488; }
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit { background:#0c1525; border:1px solid #334155; border-radius:5px; padding:7px; selection-background-color:#0f766e; }
QListWidget, QTableWidget { background:#101d30; border:1px solid #2c3e56; border-radius:6px; alternate-background-color:#152439; }
QListWidget::item { padding:12px 8px; border-radius:5px; }
QListWidget::item:selected, QTableWidget::item:selected { background:#164e63; }
QHeaderView::section { background:#1e3049; border:0; padding:8px; }
QTabWidget::pane { border:1px solid #2c3e56; border-radius:7px; }
QTabBar::tab { background:#17243a; padding:11px 19px; }
QTabBar::tab:selected { background:#23425a; color:#8df0d7; }
QCheckBox { spacing:8px; padding:5px 0; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #64748b; border-radius:3px; background:#0c1525; }
QCheckBox::indicator:checked { background:#0d9488; border:2px solid #5eead4; }
QMenu { background:#1e293b; border:1px solid #475569; padding:5px; }
QMenu::item { padding:8px 20px; }
QMenu::item:selected { background:#0f766e; }
QScrollArea { border:0; }
QToolTip { color:#f8fafc; background:#334155; border:1px solid #64748b; }
"""


def button(text, fn, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
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


def path_field(line, directory=True, title="选择文件夹"):
    def choose():
        if directory:
            value = QFileDialog.getExistingDirectory(line, title, line.text())
        else:
            value, _ = QFileDialog.getOpenFileName(line, title, line.text(), "所有文件 (*)")
        if value:
            line.setText(value)
    return row(line, button("浏览…", choose))


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#14b8a6"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(3, 3, 58, 58, 16, 16)
    painter.setBrush(QColor("#0f172a"))
    for x, height in [(16, 16), (25, 34), (34, 44), (43, 24)]:
        painter.drawRoundedRect(x, (64 - height) // 2, 5, height, 2, 2)
    painter.end()
    return QIcon(pixmap)


from .rules_ui import RuleDialog


class Window(LibraryMixin, DialogueMixin, QMainWindow):
    job_done = Signal(object, object, object)
    hook_event = Signal(str, str)
    progress = Signal(str)

    def __init__(self, store=None, hooks=True):
        super().__init__()
        self.store = store or Store()
        self.setWindowTitle("壁纸声伴 · Wallpaper Companion")
        self.setWindowIcon(app_icon())
        self.resize(1180, 840)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1180, available.width() - 60), min(840, available.height() - 60))
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="companion")
        self.job_done.connect(self.finish_job)
        self.progress.connect(self.log)
        self.query_busy = False
        self.tts_busy = False
        self.generation_cancel = threading.Event()
        self.quitting = False
        self.editing_id = None
        self.edit_rules = []
        self.active_id = None
        self.current = dict(path="", title="正在检测当前壁纸…", running=False)
        self.paused = False
        self.fullscreen = False
        self.original_audio = dict(state="unknown", detail="尚未检测原壁纸音频")
        self.original_audio_request = 0
        self.engine = RuleEngine()
        self.registry = load_extensions(self.store.config)
        for setting, mapping, fallback in [("audio_backend", self.registry.audio, "qt"),
                                           ("input_backend", self.registry.inputs, "pynput"),
                                           ("wallpaper_backend", self.registry.wallpapers, "wallpaper_engine"),
                                           ("library_backend", self.registry.libraries, "wallpaper_engine"),
                                           ("audio_detector", self.registry.audio_detectors, "builtin")]:
            if self.store.config.get(setting) not in mapping:
                self.registry.errors.append("所选扩展不可用，已回退：" + setting)
                self.store.config[setting] = fallback
        EVENTS.clear()
        EVENTS.update({key: value[0] for key, value in self.registry.events.items()})
        self.audio = self.registry.audio[self.store.config.get("audio_backend", "qt")][1](self)
        self.audio.message.connect(self.log)
        self.hooks = self.registry.inputs[self.store.config.get("input_backend", "pynput")][1](lambda event, key: self.hook_event.emit(event, key))
        self.hook_event.connect(self.input_event)
        self.build_ui()
        self.build_tray()
        self.refresh_profiles()
        self.load_settings()
        self.load_tts()
        from .help_ui import HoverHelp
        self.hover_help = HoverHelp(self)
        for error in self.registry.errors:
            self.log("扩展加载失败：" + error)
        self.audio.changed.connect(self.refresh_status)
        if hooks:
            try:
                self.hooks.start()
            except Exception as exc:
                self.log("输入监听未启动：" + str(exc))
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.detect)
        self.poll.start(self.store.config.get("poll_seconds", 4) * 1000)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self.on_tick)
        self.tick.start(1000)
        QTimer.singleShot(200, self.detect)
        QTimer.singleShot(500, self.scan_library)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 16)
        title = QLabel("壁纸声伴")
        title.setObjectName("brand")
        self.pause_button = button("暂停伴随", self.toggle_pause)
        self.help_button = button("悬停说明：开启" if self.store.config.get("hover_help", True) else "悬停说明：关闭", self.toggle_hover_help)
        layout.addWidget(row(title, hint("让当前壁纸拥有声音与回应"), self.help_button,
                             button("打开使用手册", lambda: self.open_document("USER_GUIDE.md")), self.pause_button))
        self.current_label = QLabel("正在检测…")
        self.current_label.setObjectName("current")
        self.current_label.setWordWrap(True)
        layout.addWidget(row(self.current_label, button("立即检测", self.detect)))
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)
        splitter = QSplitter()
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 10, 0)
        side.addWidget(QLabel("壁纸配置"))
        self.profiles = QListWidget()
        self.profiles.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.profiles.currentRowChanged.connect(self.select_profile)
        side.addWidget(self.profiles)
        side.addWidget(button("＋ 绑定当前壁纸", self.bind_current, True))
        side.addWidget(button("扫描 / 批量绑定壁纸…", lambda: self.tabs.setCurrentIndex(self.library_tab_index)))
        side.addWidget(row(button("新建", self.add_profile), button("删除", self.delete_profile)))
        self.manual = QCheckBox("手动使用选中配置")
        self.manual.setToolTip("关闭时随 Wallpaper Engine 当前壁纸自动切换；开启可独立测试声音。")
        self.manual.toggled.connect(self.set_manual)
        side.addWidget(self.manual)
        side.addWidget(hint("自动模式只为已绑定的壁纸播放声音。\n关闭窗口后留在系统托盘。"))
        splitter.addWidget(sidebar)
        self.tabs = QTabWidget()
        splitter.addWidget(self.tabs)
        splitter.setSizes([245, 865])
        layout.addWidget(splitter, 1)
        self.build_profile_tab()
        self.build_tts_tab()
        self.build_settings_tab()
        self.build_library_tab()
        self.build_dialogue_tab()
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(500)
        self.tabs.addTab(self.logs, "运行记录")
        self.footer = hint("独立伴随 · 音频、配置保存在自己的目录 · 输入监听不记录输入文本")
        layout.addWidget(self.footer)

    def build_profile_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        content = QVBoxLayout(inner)
        form = QFormLayout()
        self.profile_name = QLineEdit()
        self.wallpaper_path = QLineEdit()
        self.wallpaper_path.setReadOnly(True)
        self.voice_dir = QLineEdit()
        self.bgm_dir = QLineEdit()
        self.asset_dir = QLineEdit()
        self.dialogue_file = QLineEdit()
        self.dialogue_file.setReadOnly(True)
        self.original_audio_policy = QComboBox()
        for label, value in [("防冲突：有声音证据或无法确认时暂停 BGM", "safe"), ("仅发现声音证据时暂停 BGM", "detected"), ("允许伴随 BGM 播放", "allow")]:
            self.original_audio_policy.addItem(label, value)
        self.original_audio_override = QComboBox()
        for label, value in [("自动检测", "auto"), ("我确认原壁纸无声 / 已静音", "no"), ("我确认原壁纸有声音", "yes")]:
            self.original_audio_override.addItem(label, value)
        self.original_audio_label = hint("尚未检测原壁纸音频")
        self.bgm_pause_button = button("暂停当前 BGM", self.toggle_bgm)
        self.profile_enabled = QCheckBox("启用此配置")
        self.desktop_only = QCheckBox("鼠标和键盘仅在桌面前台时触发")
        self.fullscreen_mute = QCheckBox("全屏应用前台时暂停伴随声音")
        self.bgm_enabled = QCheckBox("启用文件夹 BGM")
        self.shuffle = QCheckBox("随机播放 BGM（关闭则按文件名顺序）")
        self.voice_volume = spin(0, 100, 80, "%")
        self.bgm_volume = spin(0, 100, 25, "%")
        self.bgm_volume.valueChanged.connect(self.live_bgm_volume)
        self.duck = spin(0, 100, 25, "%")
        self.global_cooldown = spin(0, 3600, 8, " 秒")
        for label, w in [("配置名称", self.profile_name), ("绑定壁纸", self.wallpaper_path),
                         ("语音文件夹", path_field(self.voice_dir)), ("BGM 文件夹", path_field(self.bgm_dir)),
                         ("播放开关", row(self.profile_enabled, self.bgm_enabled)), ("输入范围", self.desktop_only),
                         ("全屏时", self.fullscreen_mute), ("BGM 顺序", self.shuffle),
                         ("音量", row(QLabel("语音"), self.voice_volume, QLabel("BGM"), self.bgm_volume)),
                         ("说话时 BGM 保留", self.duck), ("语音全局冷却", self.global_cooldown)]:
            form.addRow(label, w)
        form.addRow("重新绑定", button("将此配置绑定到当前壁纸", self.rebind_current))
        form.addRow("资源根目录（可共享）", path_field(self.asset_dir))
        self.asset_dir.setPlaceholderText("默认使用 data 下的资源目录；需要自定义时再修改")
        form.addRow("", button("按此根目录绑定音频、BGM 和台词库", self.use_asset_directory))
        form.addRow("资源共享方式", button("分别设置语音 / BGM / 台词的共享或专用模式…", self.configure_resources))
        form.addRow("共用台词文件", self.dialogue_file)
        form.addRow("原壁纸音频策略", self.original_audio_policy)
        form.addRow("手动覆盖检测", self.original_audio_override)
        form.addRow("当前播放的音频检测", self.original_audio_label)
        form.addRow("音频检测", button("重新检测原壁纸声音", self.probe_original_audio))
        content.addLayout(form)
        content.addWidget(row(button("建立专用音频目录", self.make_audio_dirs),
                              button("打开语音目录", lambda: self.open_folder(self.voice_dir.text())),
                              button("打开 BGM 目录", lambda: self.open_folder(self.bgm_dir.text()))))
        content.addWidget(hint("可放入 WAV / MP3 / OGG / FLAC / M4A 等音频，包含子目录。新增、删除文件会在下次选曲时生效。"))
        content.addWidget(hint("到“互动规则”标签中设置鼠标、快捷键和按时间段随机播放。修改后请保存配置。"))
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        outer.addWidget(row(button("保存配置", self.save_profile, True), button("随机试听语音", self.preview_voice),
                            self.bgm_pause_button, button("下一首 BGM", self.audio.next_bgm), button("停止试听", self.audio.voice.stop)))
        self.tabs.addTab(page, "声音与互动")
        rules_page = QWidget()
        rules_layout = QVBoxLayout(rules_page)
        rules_layout.addWidget(hint("规则属于左侧选中的配置。可用不同子目录和时间段安排早安、晚安、点击回应。\n"
                                   "语音播放中不会叠加其他语音；桌面范围和全局冷却在“声音与互动”中设置。"))
        self.rules_table = QTableWidget(0, 5)
        self.rules_table.setHorizontalHeaderLabels(["启用", "规则", "触发", "时段", "来源 / 筛选"])
        self.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.setMinimumHeight(165)
        self.rules_table.cellDoubleClicked.connect(lambda r, c: self.edit_rule())
        rules_layout.addWidget(self.rules_table, 1)
        rules_layout.addWidget(row(button("＋ 添加规则", self.add_rule), button("编辑", self.edit_rule),
                              button("删除规则", self.delete_rule), button("试听选中规则", self.preview_rule)))
        rules_layout.addWidget(button("保存配置与规则", self.save_profile, True))
        rules_layout.addWidget(row(button("导入互动配置…", self.import_interaction_preset), button("导出选中配置…", self.export_interaction_preset)))
        self.tabs.addTab(rules_page, "互动规则")

    def build_tts_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.provider_choice = QComboBox()
        for provider in self.registry.speech.values():
            self.provider_choice.addItem(provider.title, provider.id)
        layout.addWidget(row(QLabel("语音生成扩展"), self.provider_choice))
        self.provider_description = hint("")
        layout.addWidget(self.provider_description)
        provider_scroll = QScrollArea()
        provider_scroll.setWidgetResizable(True)
        self.provider_fields_widget = QWidget()
        self.provider_form = QFormLayout(self.provider_fields_widget)
        self.provider_widgets = {}
        self.provider_cache = {}
        self.rendered_provider = ""
        provider_scroll.setWidget(self.provider_fields_widget)
        layout.addWidget(provider_scroll, 2)
        self.tts_output = QLineEdit()
        layout.addWidget(row(QLabel("生成保存目录"), path_field(self.tts_output)))
        self.start_api_button = button("启动本地 API", self.launch_api)
        layout.addWidget(row(button("保存接口设置", self.save_tts), button("检测连接", self.check_api),
                             self.start_api_button, button("使用当前配置的语音目录", self.use_voice_dir)))
        layout.addWidget(hint("每行一条台词，按台词保存 WAV，重名自动编号。密钥保存到系统凭据管理器；切换服务可分别保存设置。"))
        self.lines = QPlainTextEdit()
        self.lines.setPlaceholderText("欢迎回来。\n今天也辛苦了。\n早上好，新的一天开始啦。")
        layout.addWidget(self.lines, 1)
        self.generate_button = button("生成并保存语音", self.generate_audio, True)
        layout.addWidget(row(self.generate_button, button("打开保存目录", lambda: self.open_folder(self.tts_output.text()))))
        self.tts_status = QLabel("尚未检测连接")
        self.tts_status.setWordWrap(True)
        layout.addWidget(self.tts_status)
        self.tabs.addTab(page, "生成语音")
        self.provider_choice.currentIndexChanged.connect(self.switch_provider)

    def stash_provider(self):
        if self.rendered_provider:
            values = {}
            for key, widget in self.provider_widgets.items():
                if isinstance(widget, QPlainTextEdit):
                    values[key] = widget.toPlainText().strip()
                elif isinstance(widget, QDoubleSpinBox):
                    values[key] = widget.value()
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
            else:
                widget = QLineEdit(str(value))
                if field.kind == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
                    if not value:
                        try:
                            from .secrets import read_secret
                            widget.setText(read_secret(provider.id if field.key == "api_key" else provider.id + ":" + field.key))
                        except Exception as exc:
                            self.log("无法读取系统密钥存储：" + str(exc))
            from .help_ui import PROVIDER_HELP
            widget.setToolTip(field.help or PROVIDER_HELP.get(field.key, "填写“" + field.label + "”，参数由此语音扩展定义。"))
            if isinstance(widget, QLineEdit):
                widget.setPlaceholderText(field.help)
            self.provider_widgets[field.key] = widget
            display = path_field(widget, field.kind == "directory") if field.kind in {"file", "directory"} else widget
            self.provider_form.addRow(field.label, display)
        self.provider_description.setText(provider.description)
        self.start_api_button.setVisible(provider.start is not None and provider.id != "gpt_sovits")
        from .help_ui import annotate_controls
        annotate_controls(self)

    def build_settings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.we_dir = QLineEdit()
        self.workshop_dir = QLineEdit()
        self.monitor = spin(0, 20, 0)
        self.poll_seconds = spin(2, 60, 4, " 秒")
        self.backend_combos = {}
        for setting, title, mapping in [("wallpaper_backend", "壁纸识别扩展", self.registry.wallpapers),
                                         ("audio_backend", "音频播放扩展", self.registry.audio),
                                         ("input_backend", "输入事件扩展", self.registry.inputs),
                                         ("library_backend", "壁纸库扫描扩展", self.registry.libraries),
                                         ("audio_detector", "原壁纸声音检测扩展", self.registry.audio_detectors)]:
            combo = QComboBox()
            for identifier, (label, _) in mapping.items():
                combo.addItem(label, identifier)
            combo.setToolTip(title + "：选择已加载的后端，保存后重启应用。")
            self.backend_combos[setting] = combo
            form.addRow(title, combo)
        form.addRow("WE 安装目录（只读使用）", path_field(self.we_dir))
        form.addRow("工坊目录（写入保护）", path_field(self.workshop_dir))
        form.addRow("跟随显示器（从 0 开始）", self.monitor)
        form.addRow("壁纸检测间隔", self.poll_seconds)
        layout.addLayout(form)
        layout.addWidget(button("保存运行设置", self.save_settings, True))
        self.startup_button = button("检测开机自启状态…", self.toggle_startup)
        layout.addWidget(self.startup_button)
        from .startup import startup_enabled
        try:
            self.refresh_startup_button(startup_enabled())
        except OSError as exc:
            self.startup_button.setText("开机自启状态读取失败（点击重试）")
        self.ffprobe_path = QLineEdit(self.store.config.get("ffprobe", ""))
        layout.addWidget(row(QLabel("ffprobe（留空自动发现）"), path_field(self.ffprobe_path, False)))
        layout.addWidget(QLabel("本地扩展（勾选后保存，重启生效）"))
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
        layout.addWidget(hint("从可信来源将扩展 .py 文件放入下方按钮打开的目录后重启即可列出。启用的 Python 扩展拥有本程序的文件/网络权限。内置功能无需勾选。"))
        layout.addWidget(button("打开扩展目录", lambda: self.open_folder(str(PLUGIN_DIR))))
        layout.addWidget(hint("自动识别使用官方 getWallpaper 命令；不运行修改壁纸、音量或暂停 WE 的命令。\n"
                              "伴随暂停和全屏静音只控制本程序的声音。每次只跟随一台显示器。\n\n"
                              "关闭窗口会最小化到托盘；右键托盘图标可以暂停或退出。\n"
                              "开机自启由上方按钮选择，仅当前用户登录后运行；不记录键盘文本。云端语音发送台词至配置的服务。\n\n"
                              f"配置位置：{DATA / 'config.json'}\n"
                              "复用开源组件：PySide6 / Qt Multimedia、pynput、requests、psutil。来源见 THIRD_PARTY.md。"))
        layout.addWidget(row(button("打开程序数据目录", lambda: self.open_folder(str(DATA))),
                             button("打开使用说明", lambda: self.open_document("README.md"))))
        layout.addStretch()
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setWidget(page)
        self.tabs.addTab(settings_scroll, "运行设置")

    def build_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("壁纸声伴 · 配置与音频伴随")
        menu = QMenu(self)
        menu.addAction("打开配置", self.show_window)
        self.tray_pause = menu.addAction("暂停伴随", self.toggle_pause)
        menu.addAction("暂停 / 继续 BGM", self.toggle_bgm)
        menu.addAction("下一首 BGM", self.audio.next_bgm)
        menu.addSeparator()
        menu.addAction("退出", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def log(self, text):
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
        self.log("错误：" + str(error))
        QMessageBox.warning(self, "操作未完成", str(error))

    def refresh_profiles(self, selected=None):
        selected = selected or self.editing_id
        self.profiles.blockSignals(True)
        self.profiles.clear()
        target = -1
        for i, p in enumerate(self.store.config["profiles"]):
            self.profiles.addItem(p["name"] + ("  · 已绑定" if p["wallpaper"] else "  · 未绑定"))
            self.profiles.item(i).setData(Qt.ItemDataRole.UserRole, p["id"])
            if p["id"] == selected:
                target = i
        if target < 0 and self.profiles.count():
            target = 0
        self.profiles.setCurrentRow(target)
        self.profiles.blockSignals(False)
        self.select_profile(target)
        self.manual.blockSignals(True)
        self.manual.setChecked(bool(self.store.config["manual_profile"]))
        self.manual.blockSignals(False)

    def select_profile(self, index):
        old_voice_dir = self.voice_dir.text()
        old = self.store.profile(self.editing_id)
        profiles = self.store.config["profiles"]
        new_id = profiles[index]["id"] if 0 <= index < len(profiles) else None
        if old and old["id"] != new_id and self.draft_profile() != old:
            response = QMessageBox.question(self, "配置尚未保存", "当前修改尚未保存。放弃修改并切换配置？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
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
            self.dialogue_file.clear()
            self.edit_dialogues = []
            self.render_dialogues()
            return
        p = self.store.config["profiles"][index]
        from .assets import load_dialogues
        try:
            p["dialogues"] = load_dialogues(p)
        except (ValueError, OSError) as exc:
            self.report_error("读取台词库失败，保留配置中的原文本：" + str(exc))
        self.editing_id = p["id"]
        for widget, key in [(self.profile_name, "name"), (self.wallpaper_path, "wallpaper"), (self.voice_dir, "voice_dir"), (self.bgm_dir, "bgm_dir")]:
            widget.setText(p[key])
        self.asset_dir.setText(p.get("asset_dir", ""))
        self.dialogue_file.setText(p.get("dialogue_file", ""))
        self.original_audio_policy.setCurrentIndex(max(0, self.original_audio_policy.findData(p.get("original_audio_policy", "safe"))))
        self.original_audio_override.setCurrentIndex(max(0, self.original_audio_override.findData(p.get("original_audio_override", "auto"))))
        for widget, key in [(self.profile_enabled, "enabled"), (self.desktop_only, "desktop_only"),
                            (self.fullscreen_mute, "fullscreen_mute"), (self.bgm_enabled, "bgm_enabled"), (self.shuffle, "bgm_shuffle")]:
            widget.setChecked(p.get(key, True))
        for widget, key in [(self.voice_volume, "voice_volume"), (self.bgm_volume, "bgm_volume"),
                            (self.duck, "duck_percent"), (self.global_cooldown, "global_cooldown")]:
            widget.blockSignals(True)
            widget.setValue(p[key])
            widget.blockSignals(False)
        self.edit_rules = copy.deepcopy(p["rules"])
        self.edit_dialogues = copy.deepcopy(p.get("dialogues", []))
        self.render_dialogues()
        self.render_rules()
        if not self.tts_output.text() or self.tts_output.text() == old_voice_dir:
            self.tts_output.setText(p["voice_dir"])
        if self.manual.isChecked() and self.store.config["manual_profile"] != p["id"]:
            self.set_manual(True)

    def draft_profile(self):
        p = copy.deepcopy(self.store.profile(self.editing_id))
        if not p:
            raise ValueError("请先绑定当前壁纸或新建配置")
        p.update(name=self.profile_name.text().strip() or "壁纸配置", wallpaper=self.wallpaper_path.text(),
                 voice_dir=self.voice_dir.text().strip(), bgm_dir=self.bgm_dir.text().strip(),
                 asset_dir=self.asset_dir.text().strip(), dialogue_file=self.dialogue_file.text().strip(),
                 original_audio_policy=self.original_audio_policy.currentData(), original_audio_override=self.original_audio_override.currentData(),
                 enabled=self.profile_enabled.isChecked(), desktop_only=self.desktop_only.isChecked(),
                 fullscreen_mute=self.fullscreen_mute.isChecked(), bgm_enabled=self.bgm_enabled.isChecked(),
                 bgm_shuffle=self.shuffle.isChecked(), voice_volume=self.voice_volume.value(),
                 bgm_volume=self.bgm_volume.value(), duck_percent=self.duck.value(), global_cooldown=self.global_cooldown.value(),
                 rules=copy.deepcopy(self.edit_rules), dialogues=self.collect_dialogues())
        return p

    def save_profile(self):
        try:
            from .dialogues import normalize_dialogues
            p = self.draft_profile()
            p["dialogues"] = normalize_dialogues(p["dialogues"])
            for key in ["voice_dir", "bgm_dir"]:
                if p[key] and not Path(p[key]).is_dir():
                    raise ValueError("目录不存在，请先创建或选择已有文件夹：" + p[key])
            if p.get("dialogue_file"):
                from .assets import write_dialogues
                write_dialogues(p["dialogue_file"], p["dialogues"], self.store.protected())
                for other in self.store.config["profiles"]:
                    if other["id"] != p["id"] and identity(other.get("dialogue_file", "")) == identity(p["dialogue_file"]):
                        other["dialogues"] = copy.deepcopy(p["dialogues"])
            index = next(i for i, q in enumerate(self.store.config["profiles"]) if q["id"] == p["id"])
            self.store.config["profiles"][index] = p
            self.store.save()
            self.refresh_profiles(p["id"])
            self.activate_profile(force=True)
            self.log("已保存配置：" + p["name"])
            self.render_library()
            return True
        except Exception as exc:
            self.report_error(str(exc))
            return False

    def add_profile(self):
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
        if not self.current["path"]:
            QMessageBox.information(self, "尚无当前壁纸", "请先在 Wallpaper Engine 中播放一张壁纸，再点击立即检测。也可以先新建配置并开启手动模式测试。")
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
            QMessageBox.information(self, "无法绑定", "请选中配置，并确保 Wallpaper Engine 正在播放壁纸且已检测成功。")
            return
        existing = self.store.bound_profile(self.current["path"])
        if existing and existing["id"] != self.editing_id:
            QMessageBox.information(self, "此壁纸已有配置", "请直接选择已有配置：" + existing["name"])
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
        if QMessageBox.question(self, "批量删除配置", f"删除选中的 {len(ids)} 个壁纸绑定配置？\n壁纸、语音、BGM 和共享台词文件全部保留。") != QMessageBox.StandardButton.Yes:
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
            self.log(f"已删除 {count} 个绑定，资源文件保留。")
        except Exception as exc:
            self.report_error(str(exc))

    def make_audio_dirs(self):
        self.configure_resources(dedicated=True)

    def configure_resources(self, dedicated=False):
        if not self.editing_id:
            self.report_error("请先新建或绑定配置")
            return
        try:
            from .resources_ui import ResourceDialog
            dialog = ResourceDialog(self.store, self.draft_profile(), self, dedicated)
            if dialog.exec():
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
        for widget, key in [(self.asset_dir, "asset_dir"), (self.voice_dir, "voice_dir"), (self.bgm_dir, "bgm_dir"), (self.dialogue_file, "dialogue_file")]:
            widget.setText(attached[key])
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
                self.log("保存实时 BGM 音量失败：" + str(exc))

    def toggle_bgm(self):
        profile = self.store.profile(self.active_id)
        if not profile:
            self.log("当前没有播放配置，无法切换 BGM。")
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
        profile = self.store.profile(self.active_id)
        self.original_audio = dict(state="unknown", detail="正在检测…" if profile else "当前无播放配置")
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
            done(dict(state="unknown", detail="检测失败：" + str(error)))
        self.submit(lambda: detector(config, wallpaper), done, failed)

    def apply_original_audio_policy(self):
        from .original_audio import should_block_bgm
        profile = self.store.profile(self.active_id)
        blocked = bool(profile and should_block_bgm(profile, self.original_audio))
        if hasattr(self.audio, "set_bgm_blocked"):
            self.audio.set_bgm_blocked(blocked)
        self.original_audio_label.setText(self.original_audio["detail"] + ("；防冲突暂停伴随 BGM" if blocked else ""))
        self.refresh_status()

    def refresh_startup_button(self, enabled):
        self.startup_button.setText("开机自启：已开启（点击关闭）" if enabled else "开机自启：已关闭（点击开启）")

    def toggle_startup(self):
        from .startup import startup_enabled, set_startup
        try:
            enabled = not startup_enabled()
            set_startup(enabled)
            self.refresh_startup_button(enabled)
            self.log("已开启当前用户登录自启，登录后留在托盘。" if enabled else "已关闭开机自启。")
        except Exception as exc:
            self.report_error(str(exc))

    def toggle_hover_help(self):
        enabled = not self.hover_help.enabled
        self.hover_help.set_enabled(enabled)
        self.store.config["hover_help"] = enabled
        self.help_button.setText("悬停说明：开启" if enabled else "悬停说明：关闭")
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
            QMessageBox.warning(self, "无法打开说明", "请检查程序目录内的说明文件是否完整。\n" + str(exc))
            return False

    def open_folder(self, path):
        if not path or not Path(path).is_dir():
            QMessageBox.information(self, "目录不存在", "请先选择或建立有效目录。")
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
            window = "全天" if r["start"] == r["end"] else r["start"] + "–" + r["end"]
            source = r["source"] or "语音总目录"
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
            self.report_error("请先选择要导出的配置")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出可分享互动配置", "interaction-preset.json", "互动配置 (*.json)")
        if path:
            try:
                warnings = write_preset(path, profiles, self.store.protected())
                self.log(f"已导出 {len(profiles)} 个互动配置，不包含音频和密钥：{path}")
                if warnings:
                    QMessageBox.information(self, "导出完成，请核对音频来源", "\n".join(warnings))
            except Exception as exc:
                self.report_error(str(exc))

    def import_interaction_preset(self):
        from .presets import read_preset, validate_payload
        from .presets_ui import PresetImportDialog
        path, _ = QFileDialog.getOpenFileName(self, "导入可分享互动配置", "", "互动配置 (*.json)")
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
        self.log(f"已导入 {len(result['profile_ids'])} 个配置。请核对本机语音目录并绑定壁纸。")
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
        self.preview(audio_files(self.voice_dir.text()))

    def preview(self, files):
        if not files:
            QMessageBox.information(self, "未找到语音", "目录里没有匹配的音频。请放入文件、检查规则筛选，或先到“生成语音”生成台词。")
            return
        self.audio.voice_output.setVolume(self.voice_volume.value() / 100)
        self.audio.play_voice(random.choice(files))

    def set_manual(self, enabled):
        self.store.config["manual_profile"] = (self.editing_id or "") if enabled else ""
        self.store.save()
        self.activate_profile(force=True)

    def detect(self):
        if self.query_busy:
            return
        self.query_busy = True
        query = self.registry.wallpapers[self.store.config.get("wallpaper_backend", "wallpaper_engine")][1]
        self.submit(lambda c=copy.deepcopy(self.store.config): query(c), self.detected, self.detect_error)

    def detected(self, result):
        self.query_busy = False
        self.current = result
        self.current_label.setText("当前壁纸  ·  " + result["title"] + ("\n识别来源：" + result["source"] if result.get("source", "") != "官方查询" and result.get("source") else ""))
        self.current_label.setToolTip(result["path"])
        self.activate_profile()

    def detect_error(self, error):
        self.query_busy = False
        self.current = dict(path="", title="检测失败", running=False)
        self.current_label.setText("检测失败  ·  " + str(error))
        if getattr(self, "last_detect_error", "") != str(error):
            self.log("壁纸检测失败：" + str(error))
        self.last_detect_error = str(error)
        self.activate_profile()

    def activate_profile(self, force=False):
        manual = self.store.config["manual_profile"]
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
                self.log("快捷键配置失败：" + str(exc))
            if p:
                self.log("已启用" + ("手动配置：" if manual else "壁纸配置：") + p["name"])
                if not force:
                    self.input_event("startup", "")
        self.refresh_status()

    def refresh_status(self):
        p = self.store.profile(self.active_id)
        if self.paused:
            text = "已暂停伴随声音和触发"
        elif self.fullscreen:
            text = "全屏应用中 · 伴随声音已暂停"
        elif not p:
            text = "等待绑定当前壁纸，或开启手动配置"
        elif not p.get("enabled", True):
            text = "当前配置已停用：" + p["name"]
        else:
            text = ("手动模式" if self.store.config["manual_profile"] else "自动跟随") + "  ·  " + p["name"]
            if self.audio.last_bgm:
                text += "  ·  BGM：" + self.audio.last_bgm.name
            if getattr(self.audio, "bgm_paused", False):
                text += "  ·  BGM 已手动暂停"
            elif getattr(self.audio, "bgm_blocked", False):
                text += "  ·  BGM 防冲突暂停"
        self.status_label.setText(text)
        self.bgm_pause_button.setText("继续当前 BGM" if getattr(self.audio, "bgm_paused", False) else "暂停当前 BGM")

    def toggle_pause(self):
        self.paused = not self.paused
        title = "继续伴随" if self.paused else "暂停伴随"
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
            self.log("触发：" + rule["name"])
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
                        self.log("扩展事件错误：" + str(exc))
                    self.last_extension_error = str(exc)

    def load_settings(self):
        c = self.store.config
        self.we_dir.setText(c["we_dir"])
        self.workshop_dir.setText(c["workshop_dir"])
        self.monitor.setValue(c["monitor"])
        self.poll_seconds.setValue(c["poll_seconds"])
        for setting, combo in self.backend_combos.items():
            combo.setCurrentIndex(max(0, combo.findData(c.get(setting))))

    def save_settings(self):
        try:
            self.store.config.update(we_dir=self.we_dir.text().strip(), workshop_dir=self.workshop_dir.text().strip(),
                                     monitor=self.monitor.value(), poll_seconds=self.poll_seconds.value(), ffprobe=self.ffprobe_path.text().strip())
            for setting, combo in self.backend_combos.items():
                self.store.config[setting] = combo.currentData()
            self.store.config["enabled_plugins"] = [self.plugin_list.item(i).text() for i in range(self.plugin_list.count())
                                                    if self.plugin_list.item(i).checkState() == Qt.CheckState.Checked]
            self.store.save()
            self.poll.setInterval(self.poll_seconds.value() * 1000)
            self.log("运行设置已保存；扩展和播放/输入后端变更重启后生效")
            self.detect()
            self.probe_original_audio()
        except Exception as exc:
            self.report_error(str(exc))

    def load_tts(self):
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

    def save_tts(self):
        self.stash_provider()
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
            self.store.config["tts_providers"] = sanitized
            self.store.config["tts"] = sanitized.get("gpt_sovits", self.store.config["tts"])
            self.store.save()
            self.log("语音扩展设置已保存")
            return True
        except Exception as exc:
            self.report_error(str(exc))
            return False

    def use_voice_dir(self):
        self.tts_output.setText(self.voice_dir.text())

    def check_api(self):
        settings = self.tts_settings()
        self.tts_status.setText("正在检测…")
        provider = self.registry.speech[self.provider_choice.currentData()]
        self.submit(lambda: provider.check(settings), self.api_message, self.api_error)

    def launch_api(self):
        settings = self.tts_settings()
        provider = self.registry.speech[self.provider_choice.currentData()]
        if provider.id == "gpt_sovits":
            self.api_message("本地 API 会在点击生成时自动启动，无需提前启动。")
            return
        if provider.start:
            self.submit(lambda: provider.start(settings, self.store.protected()), self.api_message, self.api_error)

    def api_message(self, message):
        self.tts_status.setText(str(message))
        self.log(str(message))

    def api_error(self, error):
        self.tts_status.setText("连接或启动失败：" + str(error))
        self.log(self.tts_status.text())

    def generate_audio(self):
        if self.tts_busy:
            return
        lines = [line.strip() for line in self.lines.toPlainText().splitlines() if line.strip()]
        output = self.tts_output.text().strip()
        try:
            if not lines:
                raise ValueError("请每行填写一条待生成台词")
            if not output:
                raise ValueError("请选择生成保存目录")
            writable_path(output, self.store.protected())
            settings = self.tts_settings()
            if not self.save_tts():
                return
            provider = self.registry.speech[self.provider_choice.currentData()]
        except Exception as exc:
            self.report_error(str(exc))
            return
        self.tts_busy = True
        self.generation_cancel.clear()
        self.generate_button.setEnabled(False)
        self.tts_status.setText(f"正在生成 {len(lines)} 条语音，请稍候…")
        protected = self.store.protected()
        self.submit(lambda: generate(settings, lines, output, protected, self.progress.emit, provider, self.generation_cancel), self.generated, self.generation_error)

    def generated(self, paths):
        self.tts_busy = False
        self.generate_button.setEnabled(True)
        self.tts_status.setText(f"已保存 {len(paths)} 条语音。放在绑定目录中的文件会自动加入播放候选。")
        for path in paths:
            self.log("已生成：" + path)

    def generation_error(self, error):
        self.tts_busy = False
        self.generate_button.setEnabled(True)
        self.tts_status.setText("生成未完成：" + str(error))
        self.report_error(str(error))

    def closeEvent(self, event):
        if self.quitting or not QSystemTrayIcon.isSystemTrayAvailable():
            event.accept()
            self.cleanup()
            QApplication.quit()
        else:
            event.ignore()
            self.hide()
            if not getattr(self, "tray_notice", False):
                self.tray.showMessage("壁纸声伴", "已在托盘继续运行；右键图标可暂停或退出。")
                self.tray_notice = True

    def quit_app(self):
        if self.tts_busy:
            if QMessageBox.question(self, "退出并取消生成", "退出将取消剩余生成并停止声伴启动的本地 API；已经保存的音频保留。继续退出？") != QMessageBox.StandardButton.Yes:
                return
        self.cleanup()
        QApplication.quit()

    def cleanup(self):
        if self.quitting:
            return
        self.quitting = True
        self.generation_cancel.set()
        from .managed_api import api
        try:
            api.shutdown()
        except Exception as exc:
            self.log("停止自建 API 失败：" + str(exc))
        self.poll.stop()
        self.tick.stop()
        self.hooks.stop()
        self.audio.stop()
        self.tray.hide()
        self.executor.shutdown(wait=False, cancel_futures=True)
