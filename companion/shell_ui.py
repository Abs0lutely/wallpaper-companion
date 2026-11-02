"""Native companion navigation, local artwork preferences, and persistent player."""
from .i18n import tr
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QListWidget, QPushButton, QScrollArea, QSizePolicy, QMenu,
    QSlider, QTabWidget, QVBoxLayout, QWidget,
)
from .file_dialogs import FileDialogs as QFileDialog

from .appearance import PINK, background_path, normalize_appearance, prepare_background, save_appearance
from .theme_ui import stylesheet


class ArtworkBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(184)
        self.image = QImage()
        self.cache = QPixmap()
        self.accent = QColor(PINK)

    def set_image(self, image):
        self.image = image
        self._rescale()
        self.update()

    def _rescale(self):
        self.cache = QPixmap.fromImage(self.image).scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation) if not self.image.isNull() else QPixmap()

    def resizeEvent(self, event):
        self._rescale()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 18, 18)
        painter.setClipPath(clip)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#392935"))
        gradient.setColorAt(1, self.accent.darker(170))
        painter.fillRect(self.rect(), gradient)
        if not self.cache.isNull():
            painter.drawPixmap((self.width() - self.cache.width()) // 2,
                               int((self.height() - self.cache.height()) * .32), self.cache)
        overlay = QLinearGradient(0, 0, self.width(), 0)
        overlay.setColorAt(0, QColor(25, 17, 27, 220))
        overlay.setColorAt(.6, QColor(25, 17, 27, 90))
        overlay.setColorAt(1, QColor(25, 17, 27, 20))
        painter.fillRect(self.rect(), overlay)


class CompanionShellMixin:
    def build_companion_shell(self):
        from .ui import button, hint, row
        root = QWidget()
        root.setObjectName("shell")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 10, 20, 10)
        title = QLabel(tr('ui.e52fa9b152e1', '壁纸声伴'))
        title.setObjectName("brand")
        header_layout.addWidget(title)
        wordmark = hint("WALLPAPER COMPANION")
        wordmark.setWordWrap(False)
        wordmark.setStyleSheet("font-size:10px; letter-spacing:1px;")
        header_layout.addWidget(wordmark)
        header_layout.addStretch()
        self.help_button = button(tr('ui.4d9a0c931f4b', '悬停说明：开启') if self.store.config.get("hover_help", True) else tr('ui.f0eddb923dcd', '悬停说明：关闭'), self.toggle_hover_help)
        header_layout.addWidget(self.help_button)
        header_layout.addWidget(button(tr('ui.3aea1202cc8a', '打开使用手册'), lambda: self.open_document("USER_GUIDE.md")))
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        from .i18n import language
        sidebar.setFixedWidth(224 if language() == "en-US" else 190)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 18, 12, 15)
        side.setSpacing(5)
        body.addWidget(sidebar)
        self.navigation = {}
        self.nav_group = QButtonGroup(self)
        for label, glyph, index in [(tr('ui.ab3938f7627e', '陪伴主页'), "♡", 0), (tr('ui.99ffa5dff575', '壁纸库'), "▧", 4),
                                     (tr('ui.4f0534b98d95', '音频库'), "♫", 6), (tr('ui.40949e0e28ee', '台词库'), "☷", 5), (tr('ui.9bb997df388a', '语音生成'), "♪", 2)]:
            nav = button(f"{glyph}   {label}", lambda checked=False, i=index: self.tabs.setCurrentIndex(i))
            nav.setObjectName("nav")
            nav.setCheckable(True)
            self.nav_group.addButton(nav)
            self.navigation[index] = nav
            side.addWidget(nav)
        side.addSpacing(16)
        self.profile_list_heading=hint(tr('ui.a154bc5ed5be', '壁纸配置 · 可多选管理'))
        side.addWidget(self.profile_list_heading)
        self.profiles = QListWidget()
        self.profiles.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.profiles.setMinimumHeight(60)
        self.profiles.setMaximumHeight(140)
        self.profiles.currentRowChanged.connect(self.select_profile)
        side.addWidget(self.profiles, 1)
        side.addWidget(button(tr('ui.25c4baf40e31', '＋ 绑定当前壁纸'), self.bind_current, True))
        manage = QPushButton(tr('ui.134891399b36', '配置管理'))
        menu = QMenu(manage)
        menu.addAction(tr('ui.76e025a95831', '新建配置'), self.add_profile)
        menu.addAction(tr('ui.bd5f7c8d592f', '删除选中配置…'), self.delete_profile)
        menu.addSeparator()
        self.scan_bind_action = menu.addAction(tr('ui.602e8ee41e62', '扫描 / 批量绑定壁纸…'), lambda: self.tabs.setCurrentIndex(self.library_tab_index))
        manage.setMenu(menu)
        side.addWidget(manage)
        side.addStretch()
        for label, glyph, index in [(tr('ui.6e55e0f207bf', '运行记录'), "≋", 7), (tr('ui.df3d58c7d84b', '设置'), "⚙", 3)]:
            nav = button(f"{glyph}   {label}", lambda checked=False, i=index: self.tabs.setCurrentIndex(i))
            nav.setObjectName("nav")
            nav.setCheckable(True)
            self.nav_group.addButton(nav)
            self.navigation[index] = nav
            side.addWidget(nav)
        side.addWidget(hint(tr('ui.36312210bd1e', '本地陪伴空间\n关闭窗口后留在托盘')))

        workspace = QWidget()
        workspace.setObjectName("workspace")
        work = QVBoxLayout(workspace)
        work.setContentsMargins(25, 18, 25, 16)
        work.setSpacing(12)
        body.addWidget(workspace, 1)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        self.page_title = QLabel(tr('ui.159bb13681fc', '属于你的陪伴时光'))
        self.page_title.setObjectName("pageTitle")
        titles.addWidget(self.page_title)
        self.page_subtitle = hint(tr('ui.66db33083bd6', '声音、音乐，还有一点温柔。'))
        titles.addWidget(self.page_subtitle)
        heading.addLayout(titles, 1)
        self.import_background_button = button(tr('ui.d171abc76927', '导入背景…'), self.choose_background)
        heading.addWidget(self.import_background_button)
        work.addLayout(heading)

        self.hero = ArtworkBanner()
        hero_layout = QVBoxLayout(self.hero)
        hero_layout.setContentsMargins(24, 19, 24, 20)
        caption = QLabel("YOUR EVERYDAY COMPANION")
        caption.setObjectName("heroCaption")
        hero_layout.addWidget(caption)
        hero_layout.addStretch()
        self.current_label = QLabel(tr('ui.e8b970bc3e05', '正在检测…'))
        self.current_label.setObjectName("current")
        self.current_label.setWordWrap(True)
        hero_layout.addWidget(self.current_label)
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        hero_layout.addWidget(self.status_label)
        self.hero.setToolTip(tr('ui.3551796ca083', '导入你喜欢的角色或壁纸图片，建立自己的陪伴空间。'))
        work.addWidget(self.hero)

        context = QHBoxLayout()
        context.addWidget(QLabel(tr('ui.37dadf4857a5', '正在编辑')))
        self.profile_picker = QComboBox()
        self.profile_picker.setMinimumContentsLength(12)
        self.profile_picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.profile_picker.currentIndexChanged.connect(self.pick_profile)
        context.addWidget(self.profile_picker, 1)
        self.manual = QCheckBox(tr('ui.e068cc5c53fe', '手动使用选中配置'))
        self.manual.setToolTip(tr('ui.d2bfc754754b', '关闭时自动跟随壁纸；开启后将选中的配置用于播放。'))
        self.manual.toggled.connect(self.set_manual)
        context.addWidget(self.manual)
        self.detect_button=button(tr('ui.14ca09ce1fd2', '立即检测'), lambda: self.detect(command=True))
        context.addWidget(self.detect_button)
        context.addWidget(button(tr("mode.label","运行模式"),lambda:self.tabs.setCurrentIndex(3)))
        work.addLayout(context)
        self.editing_context = hint("")
        work.addWidget(self.editing_context)

        self.home_switcher = QWidget()
        switch = QHBoxLayout(self.home_switcher)
        switch.setContentsMargins(0, 0, 0, 0)
        switch.setSpacing(14)
        self.home_buttons = []
        home_group = QButtonGroup(self)
        for label, section in [(tr('ui.db78bb2404bf', '声音设置'), 0), (tr('ui.a0aee4954b3e', '互动规则'), 1), (tr('ui.2825fb5b3efb', '资源与绑定'), 2)]:
            tab = button(label, lambda checked=False, s=section: self.show_home_section(s))
            tab.setObjectName("homeTab")
            tab.setCheckable(True)
            home_group.addButton(tab)
            self.home_buttons.append(tab)
            switch.addWidget(tab)
        switch.addStretch()
        work.addWidget(self.home_switcher)
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.tabs.setMinimumHeight(150)
        work.addWidget(self.tabs, 1)
        self.build_profile_tab()
        self.build_tts_tab()
        self.build_settings_tab()
        self.build_library_tab()
        self.build_dialogue_tab()
        self.build_audio_library_tab()
        from PySide6.QtWidgets import QPlainTextEdit
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(500)
        self.tabs.addTab(self.logs, tr('ui.6e55e0f207bf', '运行记录'))
        # Long provider forms and library toolbars must not set the window's
        # minimum size. Keep stable tab indices for host mixins and extensions.
        for index in (1, 2, 4, 5, 6, 7):
            title = self.tabs.tabText(index)
            content = self.tabs.widget(index)
            self.tabs.removeTab(index)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content)
            scroll.setMinimumSize(0, 0)
            self.tabs.insertTab(index, scroll, title)
        self.build_appearance_settings()
        self.tabs.currentChanged.connect(self.shell_page_changed)
        self.profile_sections.currentChanged.connect(lambda _: self.shell_page_changed(self.tabs.currentIndex()))
        self.profiles.currentRowChanged.connect(lambda _: QTimer.singleShot(0, self.refresh_shell))

        self.build_player(outer)
        self.footer = hint(tr('ui.196ce29e0738', '独立伴随 · 音频与配置保存在自己的目录 · 输入监听不记录文本'))
        self.footer.setContentsMargins(20, 3, 20, 4)
        outer.addWidget(self.footer)
        self.background_busy = False
        self.apply_appearance()
        self.shell_page_changed(0)

    def build_player(self, outer):
        from .ui import button, hint
        player = QFrame()
        self.player_container = player
        player.setObjectName("player")
        layout = QHBoxLayout(player)
        layout.setContentsMargins(22, 12, 22, 12)
        layout.setSpacing(12)
        self.album_art = QLabel("♫")
        self.album_art.setFixedSize(44, 44)
        self.album_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.album_art)
        track = QVBoxLayout()
        self.track_title = QLabel(tr('ui.8b820cb9dec3', '等待播放'))
        self.track_title.setMaximumWidth(270)
        self.track_title.setWordWrap(True)
        self.track_detail = hint(tr('ui.9404112a5fcc', '绑定壁纸，或手动启用一个配置'))
        self.track_detail.setMaximumWidth(300)
        track.addWidget(self.track_title)
        track.addWidget(self.track_detail)
        layout.addLayout(track, 1)
        self.player_bgm_button = button(tr('ui.c3812eeebd5f', '暂停 BGM'), self.toggle_bgm)
        layout.addWidget(self.player_bgm_button)
        layout.addWidget(button(tr('ui.486e42475adb', '下一首'), self.audio.next_bgm))
        volume = QVBoxLayout()
        self.player_volume_label = hint("BGM 25%")
        volume.addWidget(self.player_volume_label)
        self.player_volume = QSlider(Qt.Orientation.Horizontal)
        self.player_volume.setRange(0, 100)
        self.player_volume.setFixedWidth(110)
        self.player_volume.valueChanged.connect(self.preview_player_volume)
        self.player_volume.sliderReleased.connect(self.commit_player_volume)
        self.player_volume.actionTriggered.connect(lambda _: self.player_volume_timer.start())
        self.player_volume_timer = QTimer(self)
        self.player_volume_timer.setSingleShot(True)
        self.player_volume_timer.setInterval(350)
        self.player_volume_timer.timeout.connect(self.commit_player_volume)
        self.pending_player_volume = None
        volume.addWidget(self.player_volume)
        layout.addLayout(volume)
        self.pause_button = button(tr('ui.a555aecaab24', '暂停伴随'), self.toggle_pause)
        layout.addWidget(self.pause_button)
        for control in player.findChildren(QPushButton):
            control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        outer.addWidget(player)
        if hasattr(self.audio, "bgm"):
            self.audio.bgm.playbackStateChanged.connect(lambda _: self.refresh_shell())
            self.audio.bgm.metaDataChanged.connect(self.refresh_album_art)
            self.audio.bgm.sourceChanged.connect(lambda _: self.refresh_album_art(clear=True))
            self.audio.bgm.mediaStatusChanged.connect(lambda _: self.refresh_album_art())

    def show_home_section(self, section):
        if section == 1:
            self.tabs.setCurrentIndex(1)
        else:
            self.profile_sections.setCurrentIndex(0 if section == 0 else 1)
            self.tabs.setCurrentIndex(0)
        self.shell_page_changed(self.tabs.currentIndex())

    def shell_page_changed(self, index):
        home = index in (0, 1)
        self.hero.setVisible(home)
        self.home_switcher.setVisible(home)
        nav_index = 0 if home else index
        if nav_index in self.navigation:
            self.navigation[nav_index].setChecked(True)
        names = {0: tr('ui.159bb13681fc', '属于你的陪伴时光'), 1: tr('ui.159bb13681fc', '属于你的陪伴时光'), 2: tr('ui.a0a2a14cca67', '让台词有自己的声音'),
                 3: tr('ui.307e2177e537', '让空间更像你'), 4: tr('ui.316671b9cfe4', '我的壁纸与角色'), 5: tr('ui.fdaac06efb7e', '把想说的话留下来'),
                 6: tr('ui.e0ad716bdcbf', '听见喜欢的声音'), 7: tr('ui.6e55e0f207bf', '运行记录')}
        self.page_title.setText(names.get(index, tr('ui.e52fa9b152e1', '壁纸声伴')))
        self.page_subtitle.setText(tr('ui.66db33083bd6', '声音、音乐，还有一点温柔。') if home else tr('ui.2b8259671499', '本地陪伴空间 · 配置与资源由你掌控'))
        selected = 1 if index == 1 else (2 if self.profile_sections.currentIndex() == 1 else 0)
        self.home_buttons[selected].setChecked(True)
        self.refresh_shell()

    def pick_profile(self, index):
        if index >= 0:
            self.profiles.setCurrentRow(index)
            # A canceled unsaved-edit prompt restores both selectors.
            self.refresh_shell()

    @staticmethod
    def _label(widget, text):
        if widget.text() != text:
            widget.setText(text)

    def refresh_shell(self):
        if not hasattr(self, "track_title") or not self.isVisible():
            return
        profiles = self.store.config["profiles"]
        values = [(p["id"], p["name"]) for p in profiles]
        existing = [(self.profile_picker.itemData(i), self.profile_picker.itemText(i)) for i in range(self.profile_picker.count())]
        self.profile_picker.blockSignals(True)
        if values != existing:
            self.profile_picker.clear()
            for key, name in values:
                self.profile_picker.addItem(name, key)
        self.profile_picker.setCurrentIndex(self.profile_picker.findData(self.editing_id))
        self.profile_picker.blockSignals(False)
        active = self.store.profile(self.active_id)
        editing = self.store.profile(self.editing_id)
        display = editing if editing and (not active or editing["id"] == active["id"]) else active
        self.player_container.setVisible(bool(display and display.get("bgm_enabled", True)))
        self.bgm_pause_button.setVisible(bool(display and display.get("bgm_enabled", True)))
        if editing and active and editing["id"] != active["id"]:
            context = tr('ui.c166c0e33253', '正在编辑：{value0}  ·  当前播放：{value1}', value0=editing['name'], value1=active['name'])
        elif editing:
            context = tr('ui.cacc0ee18fce', '正在编辑当前播放配置') if active else tr('ui.3b236e623cf1', '当前仅编辑配置，尚未播放')
        else:
            context = tr('ui.640e76bf5ba3', '还没有配置，请绑定当前壁纸或新建配置。')
        self._label(self.editing_context, context)
        for slider, spin in [(self.voice_slider, self.voice_volume), (self.bgm_slider, self.bgm_volume)]:
            if not slider.isSliderDown():
                slider.blockSignals(True)
                slider.setValue(spin.value())
                slider.blockSignals(False)
        last = getattr(self.audio, "last_bgm", None)
        self._label(self.track_title, Path(last).stem if last else (active["name"] if active else tr('ui.8b820cb9dec3', '等待播放')))
        if self.paused:
            detail = tr('ui.19e7ef1108f9', '伴随已暂停')
        elif self.fullscreen:
            detail = tr('ui.066d23c474f3', '全屏应用中 · 声音已暂停')
        elif not active:
            detail = tr('ui.9404112a5fcc', '绑定壁纸，或手动启用一个配置')
        elif not active.get("enabled", True):
            detail = tr('ui.e8ec8fbb9f87', '当前配置已停用')
        elif getattr(self.audio, "bgm_blocked", False):
            detail = tr('ui.d6445388f3ea', 'BGM 防冲突暂停 · ') + self.original_audio.get("detail", "")
        elif getattr(self.audio, "bgm_paused", False):
            detail = tr('ui.be92dcb9eb88', 'BGM 已暂停 · 角色语音仍可触发')
        elif not active.get("bgm_enabled", True):
            detail = tr('ui.70cd0344165c', 'BGM 已关闭 · 角色语音仍可触发')
        else:
            detail = (tr('ui.f7736b2f6176', '角色正在说话 · ') if self.audio.busy else "") + active["name"]
        self._label(self.track_detail, detail)
        self._label(self.player_bgm_button, tr('ui.01dd4a6cb900', '继续 BGM') if getattr(self.audio, "bgm_paused", False) else tr('ui.c3812eeebd5f', '暂停 BGM'))
        self.player_bgm_button.setEnabled(bool(active))
        self.player_volume.setEnabled(bool(active))
        if not self.player_volume.isSliderDown() and self.pending_player_volume is None:
            value = active.get("bgm_volume", 25) if active else 25
            self.player_volume.blockSignals(True)
            self.player_volume.setValue(value)
            self.player_volume.blockSignals(False)
            self._label(self.player_volume_label, f"BGM {value}%")

    def refresh_album_art(self, clear=False):
        from PySide6.QtMultimedia import QMediaMetaData
        from PySide6.QtGui import QImageReader
        image = QImage()
        if not clear and hasattr(self.audio, "bgm"):
            metadata = self.audio.bgm.metaData()
            for key in (QMediaMetaData.Key.CoverArtImage, QMediaMetaData.Key.ThumbnailImage):
                candidate = metadata.value(key)
                if isinstance(candidate, QPixmap):
                    candidate = candidate.toImage()
                if isinstance(candidate, QImage) and not candidate.isNull():
                    image = candidate
                    break
            track = self.audio.bgm.source().toLocalFile()
            if image.isNull() and track:
                for name in ("cover.jpg", "cover.png", "folder.jpg", "folder.png"):
                    path = Path(track).parent / name
                    if path.is_file() and path.stat().st_size <= 8 * 1024 * 1024:
                        reader = QImageReader(str(path))
                        size = reader.size()
                        if size.isValid():
                            reader.setScaledSize(size.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio))
                            image = reader.read()
                        if not image.isNull():
                            break
        if image.isNull():
            self.album_art.clear(); self.album_art.setText("♫")
        else:
            pixmap = QPixmap.fromImage(image).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                    Qt.TransformationMode.SmoothTransformation)
            self.album_art.setPixmap(pixmap.copy((pixmap.width()-44)//2, (pixmap.height()-44)//2, 44, 44))

    def bgm_enabled_changed(self, enabled):
        if not self.editing_id or not hasattr(self, "autosave") or self.autosave.busy:
            return
        if self.autosave.flush():
            self.refresh_shell()
        else:
            self.bgm_enabled.blockSignals(True)
            self.bgm_enabled.setChecked(self.store.profile(self.editing_id).get("bgm_enabled", True))
            self.bgm_enabled.blockSignals(False)

    def preview_player_volume(self, value):
        active = self.store.profile(self.active_id)
        if not active:
            return
        if self.pending_player_volume is None or self.pending_player_volume[0] != active["id"]:
            self.pending_player_volume = (active["id"], active.get("bgm_volume", 25))
        # Preview without mutating the store until the user releases the slider.
        if hasattr(self.audio, "bgm_output"):
            duck = active.get("duck_percent", 25) / 100 if self.audio.busy else 1
            self.audio.bgm_output.setVolume(value / 100 * duck)
        self._label(self.player_volume_label, f"BGM {value}%")
        self.player_volume_timer.start()

    def commit_player_volume(self):
        if not self.pending_player_volume:
            return
        if self.player_volume.isSliderDown():
            return
        key, old = self.pending_player_volume
        self.pending_player_volume = None
        profile = self.store.profile(key)
        if not profile or key != self.active_id:
            self.refresh_shell()
            return
        value = self.player_volume.value()
        profile["bgm_volume"] = value
        try:
            self.store.save()
        except Exception as exc:
            profile["bgm_volume"] = old
            self.audio.set_volumes()
            self.refresh_shell()
            self.report_error(tr('ui.37efe54298a0', '保存播放器音量失败：') + str(exc))
            return
        if self.editing_id == key:
            self.bgm_volume.blockSignals(True)
            self.bgm_volume.setValue(value)
            self.bgm_volume.blockSignals(False)
        self.audio.set_volumes()
        self.refresh_shell()

    def build_appearance_settings(self):
        from .ui import button, hint, row
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 15, 18, 15)
        title = QLabel(tr('ui.8e14d59b28cd', '外观与背景'))
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.appearance_status = hint("")
        layout.addWidget(self.appearance_status)
        layout.addWidget(row(button(tr('ui.754b1acce291', '导入背景图片…'), self.choose_background),
                             button(tr('ui.1ffb176f0f75', '恢复默认外观'), self.reset_appearance)))
        self.auto_color = QCheckBox(tr('ui.29aecfb26626', '从背景自动提取主题色'))
        self.auto_color.setToolTip(tr('ui.8470fcf31e3c', '提取图片中的主要色相，并调成适合深色界面的柔和强调色；关闭后使用樱粉。'))
        self.auto_color.toggled.connect(self.toggle_auto_color)
        layout.addWidget(self.auto_color)
        layout.addWidget(hint(tr('ui.1da72f08a187', '图片只在本机处理，并复制到声伴的数据目录。移走原图不会影响已导入背景。')))
        self.appearance_card = card
        self.tabs.widget(3).widget().layout().insertWidget(0, card)

    def apply_appearance(self, image=None):
        settings = normalize_appearance(self.store.config.get("appearance"))
        accent = settings["accent"] if settings["auto_color"] else PINK
        self.setProperty("companionAccent", accent)
        self.setStyleSheet(stylesheet(accent))
        self.hero.accent = QColor(accent)
        target = background_path(self.store, settings)
        image = image if image is not None else QImage(str(target)) if target and target.is_file() else QImage()
        self.hero.set_image(image)
        self.refresh_album_art()
        self.auto_color.blockSignals(True)
        self.auto_color.setChecked(settings["auto_color"])
        self.auto_color.blockSignals(False)
        if target and image.isNull():
            description = tr('ui.4e8cdb3de88d', '背景文件不可用，已使用默认底色。可重新导入。')
        else:
            description = (tr('ui.93f86d8d65a0', '自定义背景') if target else tr('ui.acd91815cc19', '默认背景')) + f" · {tr('ui.661499ed97e8', '自动配色') if settings['auto_color'] else tr('ui.abeb3dd78a77', '固定樱粉')} · {accent.upper()}"
        self.appearance_status.setText(description)

    def choose_background(self):
        source, _ = QFileDialog.getOpenFileName(self, tr('ui.cb1c66e02da4', '导入背景图片'), "", tr('ui.214242addd61', '图片 (*.png *.jpg *.jpeg *.webp *.bmp);;所有文件 (*)'))
        if source:
            self.import_background(source)

    def import_background(self, source):
        if self.background_busy:
            return
        self.background_busy = True
        self.import_background_button.setEnabled(False)
        self.appearance_card.setEnabled(False)
        self.appearance_status.setText(tr('ui.94dd2bc3c938', '正在本机读取背景并提取配色…'))
        def ready(prepared):
            try:
                settings = normalize_appearance(self.store.config.get("appearance"))
                settings.update(background=prepared["name"], accent=prepared["accent"])
                save_appearance(self.store, settings, prepared)
                self.apply_appearance(prepared["image"])
                self.log(tr('ui.69b35caa9522', '背景已导入并保存在本机数据目录。'))
            except Exception as exc:
                self.apply_appearance()
                self.report_error(tr('ui.d33b7d211354', '背景导入失败：') + str(exc))
            finally:
                self.background_busy = False
                self.import_background_button.setEnabled(True)
                self.appearance_card.setEnabled(True)
        def failed(error):
            self.background_busy = False
            self.import_background_button.setEnabled(True)
            self.appearance_card.setEnabled(True)
            self.apply_appearance()
            self.report_error(tr('ui.d33b7d211354', '背景导入失败：') + str(error))
        self.submit(lambda: prepare_background(source), ready, failed)

    def toggle_auto_color(self, enabled):
        settings = normalize_appearance(self.store.config.get("appearance"))
        settings["auto_color"] = enabled
        try:
            save_appearance(self.store, settings)
        except Exception as exc:
            self.report_error(tr('ui.5aab3f85181d', '保存外观失败：') + str(exc))
        self.apply_appearance(self.hero.image)

    def reset_appearance(self):
        try:
            save_appearance(self.store, {})
        except Exception as exc:
            self.report_error(tr('ui.0ff6b066637f', '恢复外观失败：') + str(exc))
        self.apply_appearance()
