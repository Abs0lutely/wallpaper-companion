"""Opt-in hover help for native controls, including dynamically created dialogs."""
import weakref

from PySide6.QtCore import QObject, QEvent, QTimer, QPoint, QRect
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QWidget, QToolTip, QPushButton, QLineEdit,
    QPlainTextEdit, QComboBox, QAbstractSpinBox, QCheckBox, QTableWidget, QListWidget, QTabWidget)
import shiboken6

CONTROL_HELP = {
    "profile_name": "给当前壁纸配置起名字，不会重命名原壁纸文件。",
    "wallpaper_path": "当前配置绑定的壁纸入口，只读；用重新绑定按钮更换。",
    "voice_dir": "播放语音的总目录，包含子目录；支持手动放入下载音频。",
    "bgm_dir": "伴随 BGM 的音乐目录，包含子目录；留空则没有伴随音乐。",
    "asset_dir": "新配置默认使用 data 下的共享资源，无需填写；可选自定义目录，或通过目录模式弹窗分别选择共享和专用。",
    "dialogue_file": "共享台词 JSON 文件；保存台词会影响引用同一文件的其他配置。",
    "profile_enabled": "关闭后此配置的自动语音和伴随 BGM 都停止。",
    "bgm_enabled": "仅控制此配置是否播放伴随 BGM，互动语音仍可使用。",
    "desktop_only": "开启后，鼠标和键盘只在桌面前台时触发，其他软件内不响应。",
    "fullscreen_mute": "全屏应用前台时暂停本程序声音，不更改 WE 自身设置。",
    "shuffle": "开启为随机选曲，关闭按文件名顺序播放。",
    "voice_volume": "互动语音的播放音量，保存配置后应用。",
    "bgm_volume": "当前播放配置的 BGM 音量即时生效并保存；未播放配置需保存。",
    "duck": "语音播放期间保留正常 BGM 音量的百分比，0% 表示暂时静音 BGM。",
    "global_cooldown": "同一配置的任意两次自动语音之间至少间隔这些秒数。",
    "original_audio_policy": "根据原壁纸声音证据决定是否只暂停伴随 BGM。",
    "original_audio_override": "已自行静音原壁纸时可确认无声，覆盖自动检测判断。",
    "manual": "使用左侧选中配置，暂时不随 WE 壁纸自动切换。",
    "profiles": "选择要编辑的配置；Ctrl 或 Shift 多选后可以批量删除绑定。",
    "we_dir": "WE 安装目录，只读查询；选包含 wallpaper32/64.exe 的文件夹。",
    "workshop_dir": "创意工坊壁纸目录，用于扫描且受写入保护。",
    "monitor": "跟随哪台显示器，编号从 0 开始，一次只跟随一台。",
    "poll_seconds": "自动重新查询当前壁纸的间隔，单位为秒。",
    "ffprobe_path": "用于检查视频音轨的 ffprobe.exe；留空从 PATH 自动查找。",
    "plugin_list": "勾选并保存后重启加载可信 Python 扩展；扩展拥有本程序权限。",
    "provider_choice": "选择语音生成服务，不同提供方分别保存配置。",
    "tts_output": "普通批量生成保存 WAV 的位置，不会自动绑定到其他壁纸。",
    "lines": "每行填写一条待合成台词；只输入文字不会自动调用 API。",
    "character_choice": "选择已保存角色，恢复模型、参考音频、逐字原文和语言；选择本身不启动 API。",
    "model_pair_choice": "按目录、名称和版本提示唯一配对的候选，不代表已验证模型兼容性；选择只填入路径。",
    "reference_choice": "本项目扫描到的音频；选中后点击填入参考音频，再核对对应原文。",
    "library_search": "筛选壁纸标题、工坊 ID 和路径；筛选不会清除隐藏行的勾选。",
    "library_table": "先勾选左列再批量绑定或删除；双击已绑定项目打开配置。",
    "extra_library_roots": "附加扫描目录，每行一个；保存后也纳入写入保护。",
    "dialogue_table": "勾选参与生成的台词；双击编辑文字和分类，修改后需要保存。",
    "skip_existing_dialogue_audio": "同一分类目录里已有同名音频时跳过，减少重复合成。",
    "rules_table": "选择或双击规则进行编辑；修改后点击保存配置与规则。",
    "audio_scope": "选择共享语音/BGM 或某张壁纸的目录；全部目录按实际文件路径去重。",
    "audio_search": "按音频文件名、路径或目录所属配置筛选，不调用语音服务。",
    "audio_target": "导入或复制到哪个目录；也可将该目录直接引用到当前壁纸。",
    "audio_category": "可选分类子目录，例如早安；不能填写绝对路径或上级目录。",
    "audio_table": "Ctrl/Shift 多选文件；双击试听。引用配置数是使用此目录的配置数。",
    "name": "给规则起一个容易辨认的名称，不改变音频文件名。",
    "enabled": "决定此规则或台词是否参与自动触发/生成。",
    "event": "选择鼠标、快捷键、定时随机或其他已加载事件。",
    "hotkey": "点击录制后直接按键或组合键，例如 Ctrl + Alt + H；此框只读，无需填写格式。",
    "trigger_category": "先选择按时间触发或按事件触发，只显示对应选项。",
    "time_mode": "选择每天固定时刻，或在指定时段内随机播放。",
    "event_family": "事件分为鼠标、键盘和壁纸/扩展事件。",
    "mouse_action": "选择鼠标按键或滚轮动作，不需要设置键盘快捷键。",
    "keyboard_mode": "指定按键需要录制；任意按键不区分具体键。",
    "record_button": "点击后直接按想绑定的键或组合键；Esc 或取消录制保留原绑定。",
    "at": "程序运行到此分钟时触发，每天一次；关闭期间不补播。",
    "source_mode": "选择语音总目录、台词分类，或自己选择音频文件/文件夹。",
    "source_category": "分类与语音总目录中的子目录名对应，可选择或填写。",
    "source": "留空使用语音总目录，也可填相对子目录或单个音频文件。",
    "keyword": "仅从文件名包含此文字的音频中选择，留空不筛选。",
    "start": "生效起始时间；与结束相同表示全天，允许跨午夜。",
    "end": "生效结束时间不包含在范围内；与起始相同表示全天。",
    "cooldown": "本条规则成功播放后，至少等待这些秒数才能再次触发。",
    "low": "定时随机的最短间隔，至少 5 秒。",
    "high": "定时随机的最长间隔，不能小于最短间隔。",
    "mode": "选择共享音频、共享完整资源，或每张壁纸独立资源目录。",
    "asset": "共享完整资源的根目录，会使用其 voice、bgm 和 dialogues.json。",
    "voice": "共享模式使用的现有语音目录。",
    "bgm": "共享模式使用的现有 BGM 目录，可留空。",
    "template": "只为新绑定复制此配置的音量、台词和规则，已有绑定不替换规则。",
    "update_existing": "明确允许为已绑定项目更新资源目录；不删除旧资源文件。",
    "category": "决定分类生成的子目录，也可自行输入新的有效分类名。",
    "text": "此条台词的文字，生成后用台词命名 WAV 文件。",
    "help_button": "打开或关闭所有控件的延迟悬停说明，选择会自动保存。",
}

BUTTON_HELP = {
    "暂停伴随": "同时暂停本程序的语音触发和 BGM，不暂停 WE。",
    "立即检测": "立刻重新查询当前显示器的壁纸。",
    "＋ 绑定当前壁纸": "为当前识别的壁纸创建配置和专用资源目录。",
    "扫描 / 批量绑定壁纸…": "打开壁纸库，搜索、勾选后批量管理绑定。",
    "新建": "建立未绑定配置，可手动测试或稍后绑定到当前壁纸。",
    "删除": "删除选中的配置或台词；配置删除不会删除任何资源文件。",
    "保存配置": "保存当前壁纸的目录、音量、台词和互动设置。",
    "随机试听语音": "从当前编辑的语音目录随机播放一条，用于检查音频。",
    "暂停当前 BGM": "只暂停或恢复当前配置的伴随音乐，不打断互动语音。",
    "下一首 BGM": "切换当前配置的下一首伴随音乐；暂停或防冲突时不会强制播放。",
    "停止试听": "停止本程序当前语音，BGM 保持原状态。",
    "将此配置绑定到当前壁纸": "把当前配置绑定到检测到的壁纸；已有其他配置时会提示。",
    "按此根目录绑定音频、BGM 和台词库": "使用同一根目录下的 voice、bgm、dialogues.json 并保存绑定。",
    "重新检测原壁纸声音": "后台检查当前播放壁纸的音轨或素材证据，不播放原音频。",
    "建立专用音频目录": "选择目录模式并保存后，还需核对配置名及路径并二次确认；取消不创建目录或修改绑定，旧文件保留。",
    "共享 / 专用目录设置…": "分别设置语音、BGM 和台词使用共享、专用或当前自定义路径。",
    "刷新音频库": "重新扫描共享目录和已配置的壁纸目录，不启动本地语音 API。",
    "导入音频文件…": "复制所选文件到目标目录，保留原文件，同名自动编号。",
    "复制所选到目标": "将列表中选中的音频复制到下方目标及分类目录，不移动原文件。",
    "试听所选": "试听选中的第一个音频，不生成新语音。",
    "移入回收站…": "确认后移入系统回收站；共享文件会影响其他使用者，失败时不永久删除。",
    "保存共享根目录": "更改新绑定的共享默认目录，不会重写现有壁纸的路径。",
    "保存角色": "保存当前角色的模型、参考音频、原文、语言和项目参数，不启动或加载 API。",
    "另存为…": "把当前角色字段另存为一个新角色名称，保留原预设。",
    "删除角色": "仅移除角色预设，保留全部模型、参考音频和台词文件。",
    "扫描本地模型": "只读扫描项目中的 ckpt/pth 权重和参考音频，不导入模型、不启动 API。",
    "填入参考音频": "把扫描列表中的音频路径填入参考音频字段，不自动猜测台词。",
    "读取同名原文": "仅尝试读取参考音频同名的 lab 或 txt；仍需人工核对逐字一致。",
    "＋ 添加规则": "添加鼠标、快捷键、时间段等语音触发规则。",
    "编辑": "编辑选中的规则或台词；完成后还需保存配置。",
    "删除规则": "从当前编辑配置移除选中规则，保存后生效。",
    "试听选中规则": "忽略时间和冷却，检查此规则是否能找到并播放音频。",
    "保存配置与规则": "保存当前规则和其他壁纸设置，重新应用当前播放配置。",
    "保存接口设置": "保存每个服务的参数，密码字段进入系统凭据管理器。",
    "检测连接": "本机服务检查 API 就绪；云服务只验证地址格式，不消耗合成额度。",
    "启动本地 API": "用所填项目和 Python 启动本机 GPT-SoVITS，模型加载需稍候。",
    "使用当前配置的语音目录": "把普通生成页的保存位置设为左侧当前编辑配置的语音目录。",
    "生成并保存语音": "调用选中的服务，逐行生成并按台词命名保存 WAV。",
    "保存运行设置": "保存安装路径、显示器、检测间隔和扩展选择。",
    "扫描壁纸库": "后台只读扫描工坊、本地创作和附加目录，不创建绑定。",
    "全选可见": "只勾选当前筛选后可见的壁纸，隐藏行保持原勾选。",
    "取消可见勾选": "只取消可见行的勾选，隐藏行保持原状态。",
    "批量创建 / 修改绑定": "按勾选壁纸统一选择共享或独立目录，默认跳过已有绑定。",
    "打开选中配置": "打开当前行已绑定的配置进行逐项修改。",
    "批量删除勾选壁纸的绑定（保留全部文件）": "仅移除勾选壁纸的声伴配置，保留壁纸和全部音频、台词。",
    "添加扫描目录…": "向附加目录输入区加入文件夹，还需点击保存目录并扫描。",
    "保存目录并扫描": "保存附加只读壁纸库目录并重新扫描。",
    "＋ 新台词": "为当前配置新增自己的台词和分类。",
    "补充默认台词": "补充未出现的默认原创台词，不覆盖现有自定义文字。",
    "保存台词库": "保存台词；若使用共享 JSON，也会影响引用同文件的配置。",
    "将勾选台词送到生成页": "把已勾选的文字填入普通生成框，仍可继续修改。",
    "按分类生成勾选台词": "按分类子目录合成勾选台词，可跳过已有同名音频。",
    "应用分类触发规则": "确认后替换编辑中的规则为默认分类触发，保存配置后生效。",
    "导入台词 JSON / TXT": "导入分类 JSON 或每行一条的 UTF-8 文本，去重后需保存。",
    "导出台词 JSON": "把当前台词库导出为可再次导入的 JSON 文件。",
    "打开使用手册": "打开逐项说明所有功能、输入框和操作示例的文档。",
    "浏览…": "打开文件或文件夹选择器，把选中路径填入相邻输入框。",
    "录制按键": "点击后在此弹窗按下想绑定的组合键，Esc 或取消录制保留原绑定。",
    "取消录制": "退出按键录制，保留此前的绑定。",
    "导入互动配置…": "预览 JSON 中的规则、台词和播放设置，选择新建或应用到现有配置。",
    "导出选中配置…": "导出左侧选中配置的规则、台词和播放参数，不包含音频、密钥或本机路径。",
}

PROVIDER_HELP = {
    "gpt_weights": "选择配套 GPT .ckpt，可填写项目相对路径；与 SoVITS 同时留空沿用 API 当前模型。",
    "sovits_weights": "选择配套 SoVITS .pth，可填写项目相对路径。只在生成时加载，扫描不读取权重内容。",
    "allow_external_model_switch": "默认关闭。勾选后允许生成时更换外部 API 的全局模型，可能影响其他连接该接口的软件。",
    "url": "填写该服务的完整合成/API 地址，本机 GPT-SoVITS 通常为 http://127.0.0.1:9880。",
    "project": "本机 GPT-SoVITS 项目目录，启动 API 时使用，不是音频保存目录。",
    "python": "可选运行 GPT-SoVITS 的 python.exe；留空尝试项目的 runtime/python.exe。",
    "reference": "选择与当前角色模型匹配的参考音频。",
    "prompt": "逐字填写参考音频实际说的话，不是待生成台词。",
    "text_lang": "待合成台词语言代码，如 zh、en、ja。",
    "prompt_lang": "参考音频原文的语言代码，如 zh、en、ja。",
    "speed": "普通语速为 1.0，范围 0.5–2.0。",
    "api_key": "填写服务密钥；保存到 Windows 凭据管理器，不写入配置 JSON。",
    "key_env": "可选密钥环境变量名，不是密钥本身，例如 AZURE_SPEECH_KEY。",
    "voice": "服务方提供的音色标识，不是本地音频文件名。",
    "model": "服务方支持的 TTS 模型标识，请按该服务文档填写。",
    "locale": "微软音色的语言区域，例如 zh-CN。",
}


def annotate_controls(root):
    for name, text in CONTROL_HELP.items():
        widget = getattr(root, name, None)
        if isinstance(widget, QWidget):
            widget.setToolTip(widget.property("help_override") or text)
    for widget in root.findChildren(QWidget):
        if isinstance(widget, QPushButton) and widget.text() in BUTTON_HELP:
            widget.setToolTip(BUTTON_HELP[widget.text()])
        if widget.toolTip():
            continue
        if isinstance(widget, QPushButton):
            text = widget.text()
            if text.startswith("打开"):
                widget.setToolTip("在系统中打开对应的目录或说明文件，方便查看与管理。")
            elif text.startswith("开机自启"):
                widget.setToolTip("选择是否在当前用户登录后后台启动声伴，关闭只移除本程序启动项。")
            else:
                widget.setToolTip("执行此项操作；详细步骤可在使用手册中查看。")
        elif isinstance(widget, QLineEdit):
            if isinstance(widget.parentWidget(), (QAbstractSpinBox, QComboBox)):
                continue
            widget.setToolTip(widget.placeholderText() or "填写此项参数；相邻名称说明用途，修改后按页面保存。")
        elif isinstance(widget, QPlainTextEdit):
            widget.setToolTip("只读显示当前内容、预览或运行记录。" if widget.isReadOnly() else widget.placeholderText() or "可编辑多行文字；修改后需要使用本页保存按钮。")
        elif isinstance(widget, QComboBox):
            widget.setToolTip("从列表选择此项设置，修改后按本页说明保存。")
        elif isinstance(widget, QCheckBox):
            widget.setToolTip("勾选开启此项，取消勾选关闭；修改后按页面说明保存。")
        elif isinstance(widget, QAbstractSpinBox):
            widget.setToolTip("输入数值或使用上下箭头调整，范围和单位由此控件限制。")
        elif isinstance(widget, (QTableWidget, QListWidget)):
            widget.setToolTip("选择列表项目进行管理，具体操作见下方按钮。")
        elif isinstance(widget, QTabWidget):
            widget.setToolTip("切换功能页面，编辑后记得保存相应配置。")


class HoverHelp(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.enabled = bool(window.store.config.get("hover_help", True))
        self.target = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.show_pending)
        QApplication.instance().installEventFilter(self)
        annotate_controls(window)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.timer.stop()
        QToolTip.hideText()

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.ToolTip:
            return True  # use our fixed delay; also suppress existing tooltips when disabled
        if isinstance(obj, QWidget):
            if kind == QEvent.Type.Show and (obj is self.window or obj.parent() is self.window):
                annotate_controls(obj)
            elif kind == QEvent.Type.Enter and self.enabled:
                widget = obj
                while widget and not widget.toolTip():
                    widget = widget.parentWidget()
                if widget:
                    self.target = weakref.ref(widget)
                    self.timer.start()
            elif kind in {QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress}:
                self.timer.stop()
                QToolTip.hideText()
        return False

    def show_pending(self):
        widget = self.target() if self.target else None
        if not self.enabled or widget is None or not shiboken6.isValid(widget) or not widget.isVisible():
            return
        hovered = QApplication.widgetAt(QCursor.pos())
        if hovered is None or (hovered is not widget and not widget.isAncestorOf(hovered)):
            return
        text = " ".join(widget.toolTip().split())
        QToolTip.showText(QCursor.pos() + QPoint(12, 18), text, widget, QRect(), 5000)
