"""Companion profile cards and advanced resources, retaining the host's controls."""
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QScrollArea, QTabWidget,
    QTableWidget, QVBoxLayout, QWidget, QSlider, QStyle, QStyleOptionFocusRect)


class ToggleSwitch(QCheckBox):
    """A native keyboard-accessible checkbox with a quiet, right-aligned switch."""
    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 55, 32)

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor(self.window().property("companionAccent") or "#edb2c4")
        p.setPen(QColor("#f3edf0") if self.isEnabled() else QColor("#817787"))
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width() - 48)
        p.drawText(self.rect().adjusted(0, 0, -48, 0), Qt.AlignmentFlag.AlignVCenter, text)
        track = QRectF(self.width() - 34, (self.height() - 19) / 2, 32, 19)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent if self.isChecked() else QColor("#514653"))
        p.drawRoundedRect(track, 9.5, 9.5)
        p.setBrush(QColor("#281821") if self.isChecked() else QColor("#e6dce8"))
        p.drawEllipse(QRectF(track.left() + (16 if self.isChecked() else 3), track.top() + 3, 13, 13))
        if self.hasFocus():
            focus = QStyleOptionFocusRect()
            focus.initFrom(self)
            focus.rect = self.rect().adjusted(1, 1, -1, -1)
            self.style().drawPrimitive(QStyle.PrimitiveElement.PE_FrameFocusRect, focus, p, self)


def section(title):
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(9)
    label = QLabel(title)
    label.setObjectName("sectionTitle")
    layout.addWidget(label)
    return card, layout


def form_layout():
    form = QFormLayout()
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setVerticalSpacing(12)
    return form


def build_profile(window):
    from .ui import button, hint, path_field, row, spin
    w = window
    page = QWidget()
    page.setObjectName("page")
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    w.profile_sections = QTabWidget()
    w.profile_sections.tabBar().hide()
    outer.addWidget(w.profile_sections, 1)
    sound = QWidget()
    sound.setObjectName("page")
    sounds = QVBoxLayout(sound)
    sounds.setContentsMargins(0, 0, 0, 0)
    sounds.setSpacing(12)
    cards = QHBoxLayout()
    cards.setSpacing(14)
    sounds.addLayout(cards)

    voice_card, voice = section("声音的分寸")
    w.voice_volume = spin(0, 100, 80, "%")
    w.bgm_volume = spin(0, 100, 25, "%")
    w.bgm_volume.valueChanged.connect(w.live_bgm_volume)
    w.duck = spin(0, 100, 25, "%")
    w.global_cooldown = spin(0, 3600, 8, " 秒")
    volume_form = form_layout()
    w.voice_slider = QSlider(Qt.Orientation.Horizontal)
    w.bgm_slider = QSlider(Qt.Orientation.Horizontal)
    for slider, control in [(w.voice_slider, w.voice_volume), (w.bgm_slider, w.bgm_volume)]:
        slider.setRange(0, 100)
        slider.setMinimumWidth(75)
        slider.setValue(control.value())
        slider.valueChanged.connect(control.setValue)
        control.valueChanged.connect(slider.setValue)
        control.setFixedWidth(76)
    for name, control in [("角色语音", row(w.voice_slider, w.voice_volume)), ("背景音乐", row(w.bgm_slider, w.bgm_volume)),
                          ("说话时 BGM 保留", w.duck), ("语音全局冷却", w.global_cooldown)]:
        volume_form.addRow(name, control)
    voice.addLayout(volume_form)
    voice.addWidget(hint("语音播放时自动压低音乐，不叠加新的语音。"))
    cards.addWidget(voice_card, 1)
    play_card, play = section("陪伴的方式")
    w.profile_enabled = ToggleSwitch("启用此配置")
    w.bgm_enabled = ToggleSwitch("启用背景音乐")
    w.desktop_only = ToggleSwitch("仅在桌面响应鼠标和键盘")
    w.fullscreen_mute = ToggleSwitch("全屏应用时暂停伴随声音")
    w.shuffle = ToggleSwitch("随机播放背景音乐")
    w.bundled_demo_enabled = ToggleSwitch("语音目录为空时使用随附示例")
    for control in [w.profile_enabled, w.bgm_enabled, w.desktop_only, w.fullscreen_mute, w.shuffle, w.bundled_demo_enabled]:
        play.addWidget(control)
    play.addStretch()
    cards.addWidget(play_card, 1)
    sounds.addStretch()
    sound_scroll = QScrollArea()
    sound_scroll.setWidgetResizable(True)
    sound_scroll.setWidget(sound)
    w.profile_sections.addTab(sound_scroll, "声音设置")

    resources = QWidget()
    resources.setObjectName("page")
    resource_layout = QVBoxLayout(resources)
    resource_layout.setContentsMargins(0, 0, 0, 0)
    resource_layout.setSpacing(14)
    identity_card, identity_layout = section("壁纸与配置")
    w.profile_name = QLineEdit()
    w.wallpaper_path = QLineEdit()
    w.wallpaper_path.setReadOnly(True)
    identity_form = form_layout()
    identity_form.addRow("配置名称", w.profile_name)
    identity_form.addRow("绑定壁纸", w.wallpaper_path)
    identity_form.addRow("", button("将此配置绑定到当前壁纸", w.rebind_current))
    identity_layout.addLayout(identity_form)
    resource_layout.addWidget(identity_card)

    resource_card, resource_content = section("这个角色的声音空间")
    w.voice_dir = QLineEdit()
    w.bgm_dir = QLineEdit()
    w.asset_dir = QLineEdit()
    w.asset_dir.setPlaceholderText("默认使用数据目录；需要自定义时再修改")
    w.dialogue_file = QLineEdit()
    w.dialogue_file.setReadOnly(True)
    resources_form = form_layout()
    for name, control in [("语音文件夹", path_field(w.voice_dir)), ("BGM 文件夹", path_field(w.bgm_dir)),
                          ("资源根目录（可共享）", path_field(w.asset_dir)), ("共用台词文件", w.dialogue_file)]:
        resources_form.addRow(name, control)
    resource_content.addLayout(resources_form)
    resource_content.addWidget(button("按此根目录绑定音频、BGM 和台词库", w.use_asset_directory))
    resource_content.addWidget(row(button("共享 / 专用目录设置…", w.configure_resources),
                                  button("建立专用音频目录", w.make_audio_dirs)))
    resource_content.addWidget(row(button("打开语音目录", lambda: w.open_folder(w.voice_dir.text())),
                                  button("打开 BGM 目录", lambda: w.open_folder(w.bgm_dir.text()))))
    resource_content.addWidget(hint("支持 WAV / MP3 / OGG / FLAC / M4A 等音频和子目录。切换资源方式不移动原文件。"))
    resource_layout.addWidget(resource_card)

    policy_card, policy = section("原壁纸声音与防冲突")
    w.original_audio_policy = QComboBox()
    for label, value in [("有声音证据或无法确认时暂停 BGM", "safe"), ("仅发现声音证据时暂停 BGM", "detected"), ("允许伴随 BGM 播放", "allow")]:
        w.original_audio_policy.addItem(label, value)
    w.original_audio_override = QComboBox()
    for label, value in [("自动检测", "auto"), ("我确认原壁纸无声 / 已静音", "no"), ("我确认原壁纸有声音", "yes")]:
        w.original_audio_override.addItem(label, value)
    w.original_audio_label = hint("尚未检测原壁纸音频")
    policy_form = form_layout()
    policy_form.addRow("防冲突策略", w.original_audio_policy)
    policy_form.addRow("手动覆盖检测", w.original_audio_override)
    policy.addLayout(policy_form)
    policy.addWidget(w.original_audio_label)
    policy.addWidget(button("重新检测原壁纸声音", w.probe_original_audio))
    resource_layout.addWidget(policy_card)
    resource_layout.addStretch()
    resource_scroll = QScrollArea()
    resource_scroll.setWidgetResizable(True)
    resource_scroll.setWidget(resources)
    w.profile_sections.addTab(resource_scroll, "资源与绑定")
    w.bgm_pause_button = button("暂停当前 BGM", w.toggle_bgm)
    actions = QHBoxLayout()
    actions.addWidget(button("随机试听语音", w.preview_voice))
    actions.addWidget(button("停止试听", w.audio.voice.stop))
    actions.addWidget(w.bgm_pause_button)
    actions.addStretch()
    actions.addWidget(button("保存配置", w.save_profile, True))
    outer.addLayout(actions)
    w.tabs.addTab(page, "声音与互动")

    rules_page = QWidget()
    rules_page.setObjectName("page")
    rules_layout = QVBoxLayout(rules_page)
    rules_layout.setContentsMargins(0, 0, 0, 0)
    rules_layout.addWidget(hint("属于正在编辑的配置。可按鼠标、快捷键或时间段安排回应；语音播放中不叠加。"))
    w.rules_table = QTableWidget(0, 5)
    w.rules_table.setHorizontalHeaderLabels(["启用", "规则", "触发", "时段", "来源 / 筛选"])
    w.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    w.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    w.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    w.rules_table.setMinimumHeight(100)
    w.rules_table.cellDoubleClicked.connect(lambda r, c: w.edit_rule())
    rules_layout.addWidget(w.rules_table, 1)
    rules_layout.addWidget(row(button("＋ 添加规则", w.add_rule), button("编辑", w.edit_rule),
                              button("删除规则", w.delete_rule), button("试听选中规则", w.preview_rule)))
    rules_layout.addWidget(row(button("导入互动配置…", w.import_interaction_preset),
                              button("导出选中配置…", w.export_interaction_preset),
                              button("保存配置与规则", w.save_profile, True)))
    w.tabs.addTab(rules_page, "互动规则")
