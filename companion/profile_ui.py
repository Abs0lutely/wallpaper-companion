"""Companion profile cards and advanced resources, retaining the host's controls."""
from .i18n import tr
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

    voice_card, voice = section(tr('ui.8b74f690c91e', '声音的分寸'))
    w.voice_volume = spin(0, 100, 80, "%")
    w.bgm_volume = spin(0, 100, 25, "%")
    w.bgm_volume.valueChanged.connect(w.live_bgm_volume)
    w.duck = spin(0, 100, 25, "%")
    w.global_cooldown = spin(0, 3600, 8, tr('ui.00fe8dda1fd7', ' 秒'))
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
    for name, control in [(tr('ui.b73c243fdcee', '角色语音'), row(w.voice_slider, w.voice_volume)), (tr('ui.3c3638bb300c', '背景音乐'), row(w.bgm_slider, w.bgm_volume)),
                          (tr('ui.548f57aebade', '说话时 BGM 保留'), w.duck), (tr('ui.b52ba3cf8424', '语音全局冷却'), w.global_cooldown)]:
        volume_form.addRow(name, control)
    voice.addLayout(volume_form)
    voice.addWidget(hint(tr('ui.48cbcc26706b', '语音播放时自动压低音乐，不叠加新的语音。')))
    cards.addWidget(voice_card, 1)
    play_card, play = section(tr('ui.0cfc4722cc74', '陪伴的方式'))
    w.profile_enabled = ToggleSwitch(tr('ui.55c57b52db83', '启用此配置'))
    w.bgm_enabled = ToggleSwitch(tr('ui.1968b6e357e8', '启用背景音乐'))
    w.desktop_only = ToggleSwitch(tr('ui.0b76dc1a5966', '仅在桌面响应鼠标和键盘'))
    w.fullscreen_mute = ToggleSwitch(tr('ui.dcc398064ccb', '全屏应用时暂停伴随声音'))
    w.shuffle = ToggleSwitch(tr('ui.115fcc040c9c', '随机播放背景音乐'))
    w.bundled_demo_enabled = ToggleSwitch(tr('ui.9e9c9a8f340b', '语音目录为空时使用随附示例'))
    for control in [w.profile_enabled, w.bgm_enabled, w.desktop_only, w.fullscreen_mute, w.shuffle, w.bundled_demo_enabled]:
        play.addWidget(control)
    play.addStretch()
    w.demo_language=QComboBox()
    w.demo_language.addItem("中文", "zh-CN");w.demo_language.addItem("日本語", "ja-JP")
    play.addWidget(QLabel(tr("voices.demo_language", "随附示例配音语言")));play.addWidget(w.demo_language)
    cards.addWidget(play_card, 1)
    sounds.addStretch()
    sound_scroll = QScrollArea()
    sound_scroll.setWidgetResizable(True)
    sound_scroll.setWidget(sound)
    w.profile_sections.addTab(sound_scroll, tr('ui.db78bb2404bf', '声音设置'))

    resources = QWidget()
    resources.setObjectName("page")
    resource_layout = QVBoxLayout(resources)
    resource_layout.setContentsMargins(0, 0, 0, 0)
    resource_layout.setSpacing(14)
    identity_card, identity_layout = section(tr('ui.180dafedd38c', '壁纸与配置'))
    w.profile_name = QLineEdit()
    w.wallpaper_path = QLineEdit()
    w.wallpaper_path.setReadOnly(True)
    identity_form = form_layout()
    identity_form.addRow(tr('ui.9919db867bd4', '配置名称'), w.profile_name)
    identity_form.addRow(tr('ui.78c7a0e5c724', '绑定壁纸'), w.wallpaper_path)
    identity_form.addRow("", button(tr('ui.bea66aeb786b', '将此配置绑定到当前壁纸'), w.rebind_current))
    identity_layout.addLayout(identity_form)
    resource_layout.addWidget(identity_card)

    resource_card, resource_content = section(tr('ui.37fbe316d817', '这个角色的声音空间'))
    w.voice_dir = QLineEdit()
    w.bgm_dir = QLineEdit()
    w.asset_dir = QLineEdit()
    w.asset_dir.setPlaceholderText(tr('ui.3d2cf188132d', '默认使用数据目录；需要自定义时再修改'))
    w.dialogue_file = QLineEdit()
    w.dialogue_file.setReadOnly(True)
    resources_form = form_layout()
    for name, control in [(tr('ui.06b2791d8cb3', '语音文件夹'), path_field(w.voice_dir)), (tr('ui.75611dc750be', 'BGM 文件夹'), path_field(w.bgm_dir)),
                          (tr('ui.5379ebef8363', '资源根目录（可共享）'), path_field(w.asset_dir)), (tr('ui.7a1cde72ea70', '共用台词文件'), w.dialogue_file)]:
        resources_form.addRow(name, control)
    resource_content.addLayout(resources_form)
    resource_content.addWidget(button(tr('ui.6134673974b4', '按此根目录绑定音频、BGM 和台词库'), w.use_asset_directory))
    resource_content.addWidget(row(button(tr('ui.37c6f54c4b3b', '共享 / 专用目录设置…'), w.configure_resources),
                                  button(tr('ui.6d0bdeefc5f8', '建立专用音频目录'), w.make_audio_dirs)))
    resource_content.addWidget(row(button(tr('ui.ceb5944b551e', '打开语音目录'), lambda: w.open_folder(w.voice_dir.text())),
                                  button(tr('ui.b51f9759d394', '打开 BGM 目录'), lambda: w.open_folder(w.bgm_dir.text()))))
    resource_content.addWidget(hint(tr('ui.a36102f318cf', '支持 WAV / MP3 / OGG / FLAC / M4A 等音频和子目录。切换资源方式不移动原文件。')))
    resource_layout.addWidget(resource_card)

    policy_card, policy = section(tr('ui.8d4d07151dba', '原壁纸声音与防冲突'))
    w.original_audio_policy = QComboBox()
    for label, value in [(tr('ui.3c7fc3b8a438', '有声音证据或无法确认时暂停 BGM'), "safe"), (tr('ui.14ccc93f4fc7', '仅发现声音证据时暂停 BGM'), "detected"), (tr('ui.d5aa65c34e76', '允许伴随 BGM 播放'), "allow")]:
        w.original_audio_policy.addItem(label, value)
    w.original_audio_override = QComboBox()
    for label, value in [(tr('ui.3b89fd6b0ced', '自动检测'), "auto"), (tr('ui.91bc1eeff11b', '我确认原壁纸无声 / 已静音'), "no"), (tr('ui.8bdc6fda7e2e', '我确认原壁纸有声音'), "yes")]:
        w.original_audio_override.addItem(label, value)
    w.original_audio_label = hint(tr('ui.420b7c1e3709', '尚未检测原壁纸音频'))
    policy_form = form_layout()
    policy_form.addRow(tr('ui.97168c73fbeb', '防冲突策略'), w.original_audio_policy)
    policy_form.addRow(tr('ui.dfb5f46666bc', '手动覆盖检测'), w.original_audio_override)
    policy.addLayout(policy_form)
    policy.addWidget(w.original_audio_label)
    policy.addWidget(button(tr('ui.cba069c906d6', '重新检测原壁纸声音'), w.probe_original_audio))
    resource_layout.addWidget(policy_card)
    resource_layout.addStretch()
    resource_scroll = QScrollArea()
    resource_scroll.setWidgetResizable(True)
    resource_scroll.setWidget(resources)
    w.profile_sections.addTab(resource_scroll, tr('ui.2825fb5b3efb', '资源与绑定'))
    w.bgm_pause_button = button(tr('ui.f6a654e97a81', '暂停当前 BGM'), w.toggle_bgm)
    actions = QHBoxLayout()
    actions.addWidget(button(tr('ui.ecd93b547925', '随机试听语音'), w.preview_voice))
    actions.addWidget(button(tr('ui.51443cd5a288', '停止试听'), w.audio.voice.stop))
    actions.addWidget(w.bgm_pause_button)
    actions.addStretch()
    actions.addWidget(button(tr('ui.6e584e3d5ce6', '保存配置'), w.save_profile, True))
    outer.addLayout(actions)
    w.tabs.addTab(page, tr('ui.b302f8d724f6', '声音与互动'))

    rules_page = QWidget()
    rules_page.setObjectName("page")
    rules_layout = QVBoxLayout(rules_page)
    rules_layout.setContentsMargins(0, 0, 0, 0)
    rules_layout.addWidget(hint(tr('ui.900dc23c3f2f', '属于正在编辑的配置。可按鼠标、快捷键或时间段安排回应；语音播放中不叠加。')))
    w.rules_table = QTableWidget(0, 5)
    w.rules_table.setHorizontalHeaderLabels([tr('ui.f4f0ead1116b', '启用'), tr('ui.1123245d1bed', '规则'), tr('ui.250bf9d56316', '触发'), tr('ui.ac3ff4261fc5', '时段'), tr('ui.d94d07746dad', '来源 / 筛选')])
    w.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    w.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    w.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    w.rules_table.setMinimumHeight(100)
    w.rules_table.cellDoubleClicked.connect(lambda r, c: w.edit_rule())
    rules_layout.addWidget(w.rules_table, 1)
    rules_layout.addWidget(row(button(tr('ui.38fa6b25b4dc', '＋ 添加规则'), w.add_rule), button(tr('ui.051836569928', '编辑'), w.edit_rule),
                              button(tr('ui.c02fdcf208b3', '删除规则'), w.delete_rule), button(tr('ui.30657ddfca7b', '试听选中规则'), w.preview_rule)))
    rules_layout.addWidget(row(button(tr('ui.6513ad089575', '导入互动配置…'), w.import_interaction_preset),
                              button(tr('ui.8f207a43caa0', '导出选中配置…'), w.export_interaction_preset),
                              button(tr('ui.729c9d5f6b87', '保存配置与规则'), w.save_profile, True)))
    w.tabs.addTab(rules_page, tr('ui.a0aee4954b3e', '互动规则'))
