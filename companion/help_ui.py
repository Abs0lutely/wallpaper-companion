"""Opt-in hover help for native controls, including dynamically created dialogs."""
from .i18n import tr
import weakref

from PySide6.QtCore import QObject, QEvent, QTimer, QPoint, QRect
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QWidget, QToolTip, QPushButton, QLineEdit,
    QPlainTextEdit, QComboBox, QAbstractSpinBox, QCheckBox, QTableView, QTableWidget, QListWidget, QTabWidget)
import shiboken6

CONTROL_HELP = {
    "run_mode": tr("mode.help", "选择跟随 WE 或无需 WE 的独立声音伴随，立即保存并可撤销；不启动语音 API。"),
    "demo_language": tr("voices.demo_help", "仅切换个人语音目录为空时的随附示例；个人音频优先，操作回应语言由其独立规则选择。"),
    "profile_name": tr('ui.d45a67a22380', '给当前壁纸配置起名字，不会重命名原壁纸文件。'),
    "wallpaper_path": tr('ui.9d95fe570fb0', '当前配置绑定的壁纸入口，只读；用重新绑定按钮更换。'),
    "voice_dir": tr('ui.1aef618cb110', '播放语音的总目录，包含子目录；支持手动放入下载音频。'),
    "bgm_dir": tr('ui.1f45899a2f43', '伴随 BGM 的音乐目录，包含子目录；留空则没有伴随音乐。'),
    "asset_dir": tr('ui.c71d4becc1c5', '新共享资源默认在程序安装目录 shared，无需填写；旧路径保持原样，也可分别选择共享或专用目录。'),
    "dialogue_file": tr('binding.help', '可编辑、浏览和解除共用台词关联；切换先预览，已有文件不覆盖，后续共享编辑影响其他引用配置。'),
    "profile_enabled": tr('ui.64a33e878c26', '关闭后此配置的自动语音和伴随 BGM 都停止。'),
    "bgm_enabled": tr('ui.aa989aa7851b', '仅控制此配置是否播放伴随 BGM，互动语音仍可使用。'),
    "desktop_only": tr('ui.82176444201d', '开启后，鼠标和键盘只在桌面前台时触发，其他软件内不响应。'),
    "fullscreen_mute": tr('ui.c84b0c3afd32', '全屏应用前台时暂停本程序声音，不更改 WE 自身设置。'),
    "shuffle": tr('ui.e5646ededcac', '开启为随机选曲，关闭按文件名顺序播放。'),
    "voice_volume": tr('ui.08f6ac394d70', '互动语音的播放音量，保存配置后应用。'),
    "bgm_volume": tr('ui.0fa876c171df', '当前播放配置的 BGM 音量即时生效并保存；未播放配置需保存。'),
    "duck": tr('ui.7bc0afb321d8', '语音播放期间保留正常 BGM 音量的百分比，0% 表示暂时静音 BGM。'),
    "global_cooldown": tr('ui.74313b5232c8', '同一配置的任意两次自动语音之间至少间隔这些秒数。'),
    "original_audio_policy": tr('ui.7178aa1b5540', '根据原壁纸声音证据决定是否只暂停伴随 BGM。'),
    "original_audio_override": tr('ui.51846110f51a', '已自行静音原壁纸时可确认无声，覆盖自动检测判断。'),
    "manual": tr('ui.89e1775c961a', '使用左侧选中配置，暂时不随 WE 壁纸自动切换。'),
    "profiles": tr('ui.5b90e21f57db', '选择要编辑的配置；Ctrl 或 Shift 多选后可以批量删除绑定。'),
    "we_dir": tr('ui.dade8a519074', 'WE 安装目录，只读查询；选包含 wallpaper32/64.exe 的文件夹。'),
    "workshop_dir": tr('ui.427a4d02069c', '创意工坊壁纸目录，用于扫描且受写入保护。'),
    "monitor": tr('ui.8001ab4732fe', '跟随哪台显示器，编号从 0 开始，一次只跟随一台。'),
    "poll_seconds": tr('ui.20769903a1b5', '自动重新查询当前壁纸的间隔，单位为秒。'),
    "ffprobe_path": tr('ui.80cc2713d96b', '用于检查视频音轨的 ffprobe.exe；留空从 PATH 自动查找。'),
    "plugin_list": tr('ui.164a4bc59e45', '勾选并保存后重启加载可信 Python 扩展；扩展拥有本程序权限。'),
    "provider_choice": tr('ui.2a27a2d23d59', '选择语音生成服务，不同提供方分别保存配置。'),
    "tts_output": tr('ui.2c2feafcf16c', '普通批量生成保存 WAV 的位置，不会自动绑定到其他壁纸。'),
    "lines": tr('ui.ad74a32a606b', '每行填写一条待合成台词；只输入文字不会自动调用 API。'),
    "character_choice": tr('ui.ffaded32c805', '选择已保存角色，恢复模型、参考音频、逐字原文和语言；选择本身不启动 API。'),
    "model_pair_choice": tr('ui.736365a900f6', '按目录、名称和版本提示唯一配对的候选，不代表已验证模型兼容性；选择只填入路径。'),
    "reference_choice": tr('ui.e917cc78c06e', '本项目扫描到的音频；选中后点击填入参考音频，再核对对应原文。'),
    "library_search": tr('ui.1597a695ed38', '筛选壁纸标题、工坊 ID 和路径；筛选不会清除隐藏行的勾选。'),
    "library_table": tr('ui.e07d12fe7a8a', '先勾选左列再批量绑定或删除；双击已绑定项目打开配置。'),
    "extra_library_roots": tr('ui.b2f6399a5215', '附加扫描目录，每行一个；保存后也纳入写入保护。'),
    "dialogue_table": tr('ui.d2c2fefc1134', '勾选参与生成的台词；双击编辑文字和分类，修改后需要保存。'),
    "skip_existing_dialogue_audio": tr('ui.5d306bd37b54', '同一分类目录里已有同名音频时跳过，减少重复合成。'),
    "rules_table": tr('ui.8cdf2f9db0fe', '选择或双击规则进行编辑；修改后点击保存配置与规则。'),
    "audio_scope": tr('ui.6e23047a17ce', '选择共享语音/BGM 或某张壁纸的目录；全部目录按实际文件路径去重。'),
    "audio_search": tr('ui.bcfac0c1ec47', '按音频文件名、路径或目录所属配置筛选，不调用语音服务。'),
    "audio_target": tr('ui.7704e749d2cb', '导入或复制到哪个目录；也可将该目录直接引用到当前壁纸。'),
    "audio_category": tr('ui.a6ec89e7843b', '可选分类子目录，例如早安；不能填写绝对路径或上级目录。'),
    "audio_table": tr('ui.037459b7b9cd', 'Ctrl/Shift 多选文件；双击试听。引用配置数是使用此目录的配置数。'),
    "name": tr('ui.ca8c91744e82', '给规则起一个容易辨认的名称，不改变音频文件名。'),
    "enabled": tr('ui.939f8931e171', '决定此规则或台词是否参与自动触发/生成。'),
    "event": tr('ui.435d06b24229', '选择鼠标、快捷键、定时随机或其他已加载事件。'),
    "hotkey": tr('ui.2dc9c1a63fb5', '点击录制后直接按键或组合键，例如 Ctrl + Alt + H；此框只读，无需填写格式。'),
    "trigger_category": tr('ui.f62c38d46a74', '先选择按时间触发或按事件触发，只显示对应选项。'),
    "time_mode": tr('ui.821c12df942b', '选择每天固定时刻，或在指定时段内随机播放。'),
    "event_family": tr('ui.02feca92dea5', '事件分为鼠标、键盘和壁纸/扩展事件。'),
    "mouse_action": tr('ui.ec0b6311d0bb', '选择鼠标按键或滚轮动作，不需要设置键盘快捷键。'),
    "keyboard_mode": tr('ui.6e40666534ac', '指定按键需要录制；任意按键不区分具体键。'),
    "record_button": tr('ui.c201fd8f821b', '点击后直接按想绑定的键或组合键；Esc 或取消录制保留原绑定。'),
    "at": tr('ui.58570694cf7f', '程序运行到此分钟时触发，每天一次；关闭期间不补播。'),
    "source_mode": tr('ui.bb9a843690dd', '选择语音总目录、台词分类，或自己选择音频文件/文件夹。'),
    "source_category": tr('ui.b70e84bb0c7c', '分类与语音总目录中的子目录名对应，可选择或填写。'),
    "source": tr('ui.6acbb404b8f0', '留空使用语音总目录，也可填相对子目录或单个音频文件。'),
    "keyword": tr('ui.7edf92b591de', '仅从文件名包含此文字的音频中选择，留空不筛选。'),
    "start": tr('ui.e20621881fd5', '生效起始时间；与结束相同表示全天，允许跨午夜。'),
    "end": tr('ui.617cd618d27b', '生效结束时间不包含在范围内；与起始相同表示全天。'),
    "cooldown": tr('ui.575f915f33dc', '本条规则成功播放后，至少等待这些秒数才能再次触发。'),
    "low": tr('ui.74a563a8b69e', '定时随机的最短间隔，至少 5 秒。'),
    "high": tr('ui.c01196610f48', '定时随机的最长间隔，不能小于最短间隔。'),
    "mode": tr('ui.5e23e4a71676', '选择共享音频、共享完整资源，或每张壁纸独立资源目录。'),
    "asset": tr('ui.de77522f06fa', '共享完整资源的根目录，会使用其 voice、bgm 和 dialogues.json。'),
    "voice": tr('ui.3e1624ceca21', '共享模式使用的现有语音目录。'),
    "bgm": tr('ui.ad22a70aa7ad', '共享模式使用的现有 BGM 目录，可留空。'),
    "template": tr('ui.5d9e06e7c466', '只为新绑定复制此配置的音量、台词和规则，已有绑定不替换规则。'),
    "update_existing": tr('ui.2a1c1673cd1e', '明确允许为已绑定项目更新资源目录；不删除旧资源文件。'),
    "category": tr('ui.ad23e1f2a72a', '决定分类生成的子目录，也可自行输入新的有效分类名。'),
    "text": tr('ui.e4a2d67f16b7', '此条台词的文字，生成后用台词命名 WAV 文件。'),
    "help_button": tr('ui.ab2c51e8ad10', '打开或关闭所有控件的延迟悬停说明，选择会自动保存。'),
}

BUTTON_HELP = {
    tr('ui.a555aecaab24', '暂停伴随'): tr('ui.cd453aa7c8d2', '同时暂停本程序的语音触发和 BGM，不暂停 WE。'),
    tr('ui.14ca09ce1fd2', '立即检测'): tr('ui.aada9b803d7b', '立刻重新查询当前显示器的壁纸。'),
    tr('ui.25c4baf40e31', '＋ 绑定当前壁纸'): tr('ui.00f24a5a2bd6', '为当前识别的壁纸创建配置和专用资源目录。'),
    tr('ui.602e8ee41e62', '扫描 / 批量绑定壁纸…'): tr('ui.7690eec2903b', '打开壁纸库，搜索、勾选后批量管理绑定。'),
    tr('ui.50ef2f4cf6a4', '新建'): tr('ui.df7eeb51ff4e', '建立未绑定配置，可手动测试或稍后绑定到当前壁纸。'),
    tr('ui.2f9daa828907', '删除'): tr('ui.dba78987d45b', '删除选中的配置或台词；配置删除不会删除任何资源文件。'),
    tr('ui.6e584e3d5ce6', '保存配置'): tr('ui.482cd4f202fa', '保存当前壁纸的目录、音量、台词和互动设置。'),
    tr('ui.ecd93b547925', '随机试听语音'): tr('ui.e5c25f99d2e6', '从当前编辑的语音目录随机播放一条，用于检查音频。'),
    tr('ui.f6a654e97a81', '暂停当前 BGM'): tr('ui.ccd915991a26', '只暂停或恢复当前配置的伴随音乐，不打断互动语音。'),
    tr('ui.7e87c201c7ab', '下一首 BGM'): tr('ui.40d786a15da4', '切换当前配置的下一首伴随音乐；暂停或防冲突时不会强制播放。'),
    tr('ui.51443cd5a288', '停止试听'): tr('ui.b681b890b972', '停止本程序当前语音，BGM 保持原状态。'),
    tr('ui.bea66aeb786b', '将此配置绑定到当前壁纸'): tr('ui.06ad86462831', '把当前配置绑定到检测到的壁纸；已有其他配置时会提示。'),
    tr('ui.6134673974b4', '按此根目录绑定音频、BGM 和台词库'): tr('ui.dff5f120bf88', '使用同一根目录下的 voice、bgm、dialogues.json 并保存绑定。'),
    tr('ui.cba069c906d6', '重新检测原壁纸声音'): tr('ui.978c43b50bd2', '后台检查当前播放壁纸的音轨或素材证据，不播放原音频。'),
    tr('ui.6d0bdeefc5f8', '建立专用音频目录'): tr('ui.70b4591451cf', '选择目录模式并保存后，还需核对配置名及路径并二次确认；取消不创建目录或修改绑定，旧文件保留。'),
    tr('ui.37c6f54c4b3b', '共享 / 专用目录设置…'): tr('ui.ebdfbf910664', '分别设置语音、BGM 和台词使用共享、专用或当前自定义路径。'),
    tr('ui.f1832518f4fd', '刷新音频库'): tr('ui.dafc70ea6172', '重新扫描共享目录和已配置的壁纸目录，不启动本地语音 API。'),
    tr('ui.dce54f102566', '导入音频文件…'): tr('ui.79aaa54e0e3b', '复制所选文件到目标目录，保留原文件，同名自动编号。'),
    tr('ui.afd5b1b068b5', '复制所选到目标'): tr('ui.2869c02a1c27', '将列表中选中的音频复制到下方目标及分类目录，不移动原文件。'),
    tr('ui.231d92a6a101', '试听所选'): tr('ui.22c9aa5aa1d6', '试听选中的第一个音频，不生成新语音。'),
    tr('ui.f4c7738d5c72', '移入回收站…'): tr('ui.5a9c2c593eb7', '确认后移入系统回收站；共享文件会影响其他使用者，失败时不永久删除。'),
    tr('ui.81d3300ba5cf', '保存共享根目录'): tr('ui.e58e9b7f4a33', '更改新绑定的共享默认目录，不会重写现有壁纸的路径。'),
    tr('ui.81854b085af3', '保存角色'): tr('ui.e6cdea89527d', '保存当前角色的模型、参考音频、原文、语言和项目参数，不启动或加载 API。'),
    tr('ui.9016c463977d', '另存为…'): tr('ui.f03af820948c', '把当前角色字段另存为一个新角色名称，保留原预设。'),
    tr('ui.5e7dadca706f', '删除角色'): tr('ui.49cd2f2a4e72', '仅移除角色预设，保留全部模型、参考音频和台词文件。'),
    tr('ui.8ed248bc6e83', '扫描本地模型'): tr('ui.0787758cf566', '只读扫描项目中的 ckpt/pth 权重和参考音频，不导入模型、不启动 API。'),
    tr('ui.9577eebd684f', '填入参考音频'): tr('ui.1f5d7a8f9f47', '把扫描列表中的音频路径填入参考音频字段，不自动猜测台词。'),
    tr('ui.cb26cdc97429', '读取同名原文'): tr('ui.cb89bed2872c', '仅尝试读取参考音频同名的 lab 或 txt；仍需人工核对逐字一致。'),
    tr('ui.38fa6b25b4dc', '＋ 添加规则'): tr('ui.65354a989934', '添加鼠标、快捷键、时间段等语音触发规则。'),
    tr('ui.051836569928', '编辑'): tr('ui.bc572ee3c183', '编辑选中的规则或台词；完成后还需保存配置。'),
    tr('ui.c02fdcf208b3', '删除规则'): tr('ui.98c3e796b534', '从当前编辑配置移除选中规则，保存后生效。'),
    tr('ui.30657ddfca7b', '试听选中规则'): tr('ui.fd9a5835683a', '忽略时间和冷却，检查此规则是否能找到并播放音频。'),
    tr('ui.729c9d5f6b87', '保存配置与规则'): tr('ui.5ead1b82b742', '保存当前规则和其他壁纸设置，重新应用当前播放配置。'),
    tr('ui.03b147f610ea', '保存接口设置'): tr('ui.e5f1ee80eec2', '保存每个服务的参数，密码字段进入系统凭据管理器。'),
    tr('ui.ab4acf8e35de', '检测连接'): tr('ui.8a48d59b8379', '本机服务检查 API 就绪；云服务只验证地址格式，不消耗合成额度。'),
    tr('ui.44f396b9cc0c', '启动本地 API'): tr('ui.3e1fe8c18d19', '用所填项目和 Python 启动本机 GPT-SoVITS，模型加载需稍候。'),
    tr('ui.e0ec003b92ec', '关闭自建 API'): tr('ui.1fa530a852f4', '只关闭声伴自己创建的 API 及子进程；外部服务仍由原程序管理。加载/生成期间不可关闭。'),
    tr('ui.327fc807c3e1', '使用当前配置的语音目录'): tr('ui.1e601942c4b9', '把普通生成页的保存位置设为左侧当前编辑配置的语音目录。'),
    tr('ui.45295cc8574e', '生成并保存语音'): tr('ui.883dc983c242', '调用选中的服务，逐行生成并按台词命名保存 WAV。'),
    tr('ui.be1f0d30be41', '保存运行设置'): tr('ui.1d057864e219', '保存安装路径、显示器、检测间隔和扩展选择。'),
    tr('ui.22d62264011f', '扫描壁纸库'): tr('ui.b921df11c7e8', '后台只读扫描工坊、本地创作和附加目录，不创建绑定。'),
    tr('ui.3d5510e6fa98', '全选可见'): tr('ui.49ec521a6514', '只勾选当前筛选后可见的壁纸，隐藏行保持原勾选。'),
    tr('ui.ebe780dbf8bb', '取消可见勾选'): tr('ui.27ae9188f09e', '只取消可见行的勾选，隐藏行保持原状态。'),
    tr('ui.7582301f85cf', '批量创建 / 修改绑定'): tr('ui.8f010cdf8817', '按勾选壁纸统一选择共享或独立目录，默认跳过已有绑定。'),
    tr('ui.927861e7b32f', '打开选中配置'): tr('ui.09aaa614c585', '打开当前行已绑定的配置进行逐项修改。'),
    tr('ui.8ce985a33630', '批量删除勾选壁纸的绑定（保留全部文件）'): tr('ui.da510161a0e4', '仅移除勾选壁纸的声伴配置，保留壁纸和全部音频、台词。'),
    tr('ui.6784c4ec422f', '添加扫描目录…'): tr('ui.657d1c32053e', '向附加目录输入区加入文件夹，还需点击保存目录并扫描。'),
    tr('ui.1a4d26554d01', '保存目录并扫描'): tr('ui.7eb5103622fd', '保存附加只读壁纸库目录并重新扫描。'),
    tr('ui.3eb41b973877', '＋ 新台词'): tr('ui.6b3c3c2f9d54', '为当前配置新增自己的台词和分类。'),
    tr('ui.ac45d38300d9', '补充默认台词'): tr('ui.131ba211ac53', '补充未出现的默认原创台词，不覆盖现有自定义文字。'),
    tr('ui.30898e1ec4d0', '保存台词库'): tr('ui.9d7b26d66707', '保存台词；若使用共享 JSON，也会影响引用同文件的配置。'),
    tr('ui.3b8118a7c3de', '将勾选台词送到生成页'): tr('ui.f1b3be1816a4', '把已勾选的文字填入普通生成框，仍可继续修改。'),
    tr('ui.7d9ab8f2b401', '应用分类触发规则'): tr('ui.1d71efecd09a', '确认后替换编辑中的规则为默认分类触发，保存配置后生效。'),
    tr('ui.5dad01da2d96', '导入台词 JSON / TXT'): tr('ui.4c537a64367f', '导入分类 JSON 或每行一条的 UTF-8 文本，去重后需保存。'),
    tr('ui.01d53f80e251', '导出台词 JSON'): tr('ui.d17fd17342e8', '把当前台词库导出为可再次导入的 JSON 文件。'),
    tr('ui.3aea1202cc8a', '打开使用手册'): tr('ui.eb091875eb13', '打开逐项说明所有功能、输入框和操作示例的文档。'),
    tr('ui.0617557e7bbc', '浏览…'): tr('ui.4f42ebc0d798', '打开文件或文件夹选择器，把选中路径填入相邻输入框。'),
    tr('ui.a89fe7c1c279', '录制按键'): tr('ui.c6d4f9161bbd', '点击后在此弹窗按下想绑定的组合键，Esc 或取消录制保留原绑定。'),
    tr('ui.1af2dcd33716', '取消录制'): tr('ui.d7bf54e22862', '退出按键录制，保留此前的绑定。'),
    tr('ui.6513ad089575', '导入互动配置…'): tr('ui.e1b4906a5368', '预览 JSON 中的规则、台词和播放设置，选择新建或应用到现有配置。'),
    tr('ui.8f207a43caa0', '导出选中配置…'): tr('ui.5d9f7397f3f5', '导出左侧选中配置的规则、台词和播放参数，不包含音频、密钥或本机路径。'),
}

PROVIDER_HELP = {
    "gpt_weights": tr('ui.e7a9e69785de', '选择配套 GPT .ckpt，可填写项目相对路径；与 SoVITS 同时留空沿用 API 当前模型。'),
    "sovits_weights": tr('ui.f79115e2ec5a', '选择配套 SoVITS .pth，可填写项目相对路径。只在生成时加载，扫描不读取权重内容。'),
    "allow_external_model_switch": tr('ui.c2edf5f0e8f7', '默认关闭。勾选后允许生成时更换外部 API 的全局模型，可能影响其他连接该接口的软件。'),
    "url": tr('ui.37b79a9a7fee', '填写该服务的完整合成/API 地址，本机 GPT-SoVITS 通常为 http://127.0.0.1:9880。'),
    "project": tr('ui.12447fd9105e', '本机 GPT-SoVITS 项目目录，启动 API 时使用，不是音频保存目录。'),
    "python": tr('ui.42ab98fddcb9', '可选运行 GPT-SoVITS 的 python.exe；留空尝试项目的 runtime/python.exe。'),
    "reference": tr('ui.847f958483d7', '选择与当前角色模型匹配的参考音频。'),
    "prompt": tr('ui.aea24b80655a', '逐字填写参考音频实际说的话，不是待生成台词。'),
    "text_lang": tr('ui.6b3c78fb6e2e', '待合成台词语言代码，如 zh、en、ja。'),
    "prompt_lang": tr('ui.f6a3e3ac01fe', '参考音频原文的语言代码，如 zh、en、ja。'),
    "speed": tr('ui.6659874e7bcb', '普通语速为 1.0，范围 0.5–2.0。'),
    "api_key": tr('ui.087b931445a8', '填写服务密钥；保存到 Windows 凭据管理器，不写入配置 JSON。'),
    "key_env": tr('ui.ff2d712339c1', '可选密钥环境变量名，不是密钥本身，例如 AZURE_SPEECH_KEY。'),
    "voice": tr('ui.cccdc740b4d4', '服务方提供的音色标识，不是本地音频文件名。'),
    "model": tr('ui.ea1c4dcf7782', '服务方支持的 TTS 模型标识，请按该服务文档填写。'),
    "locale": tr('ui.3ad74ed5928b', '微软音色的语言区域，例如 zh-CN。'),
}


def annotate_controls(root):
    for name, text in CONTROL_HELP.items():
        widget = vars(root).get(name)
        if isinstance(widget, QWidget):
            widget.setToolTip(widget.property("help_override") or text)
    for widget in root.findChildren(QWidget):
        if isinstance(widget, QPushButton) and widget.text() in BUTTON_HELP:
            widget.setToolTip(BUTTON_HELP[widget.text()])
        if widget.toolTip():
            continue
        if isinstance(widget, QPushButton):
            text = widget.text()
            if text.startswith(tr('ui.c771248e511f', '打开')):
                widget.setToolTip(tr('ui.7b225f5d082a', '在系统中打开对应的目录或说明文件，方便查看与管理。'))
            elif text.startswith(tr('ui.de38b92ad247', '开机自启')):
                widget.setToolTip(tr('ui.7c61193819a2', '选择是否在当前用户登录后后台启动声伴，关闭只移除本程序启动项。'))
            else:
                widget.setToolTip(tr('ui.c15fb1b15fd8', '执行此项操作；详细步骤可在使用手册中查看。'))
        elif isinstance(widget, QLineEdit):
            if isinstance(widget.parentWidget(), (QAbstractSpinBox, QComboBox)):
                continue
            widget.setToolTip(widget.placeholderText() or tr('ui.5800e178f4f9', '填写此项参数；相邻名称说明用途，修改后按页面保存。'))
        elif isinstance(widget, QPlainTextEdit):
            widget.setToolTip(tr('ui.f4384e4cb132', '只读显示当前内容、预览或运行记录。') if widget.isReadOnly() else widget.placeholderText() or tr('ui.cd7e50984592', '可编辑多行文字；修改后需要使用本页保存按钮。'))
        elif isinstance(widget, QComboBox):
            widget.setToolTip(tr('ui.1bd48c01915e', '从列表选择此项设置，修改后按本页说明保存。'))
        elif isinstance(widget, QCheckBox):
            widget.setToolTip(tr('ui.c368e0f07e2a', '勾选开启此项，取消勾选关闭；修改后按页面说明保存。'))
        elif isinstance(widget, QAbstractSpinBox):
            widget.setToolTip(tr('ui.cfbfc8f7d6fd', '输入数值或使用上下箭头调整，范围和单位由此控件限制。'))
        elif isinstance(widget, (QTableWidget, QListWidget)):
            if not widget.property("itemHoverDetails"):
                widget.setToolTip(tr('ui.0cbf6b85f99b', '选择列表项目进行管理，具体操作见下方按钮。'))
        elif isinstance(widget, QTabWidget):
            widget.setToolTip(tr('ui.5d098e5d3b0f', '切换功能页面，编辑后记得保存相应配置。'))


class HoverHelp(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.enabled = bool(window.store.config.get("hover_help", True))
        self.target = None
        self.detail = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.show_pending)
        QApplication.instance().installEventFilter(self)
        annotate_controls(window)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.detail = None
        self.timer.stop()
        QToolTip.hideText()

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.ToolTip:
            return True  # use our fixed delay; also suppress existing tooltips when disabled
        if isinstance(obj, QWidget):
            if kind in {QEvent.Type.Enter, QEvent.Type.MouseMove} and self.enabled:
                detail = self.table_detail(obj, QCursor.pos())
                if detail:
                    if self.detail != detail:
                        QToolTip.hideText()
                        self.detail = detail
                        self.target = weakref.ref(obj)
                        self.timer.start()
                    return False
            if kind == QEvent.Type.Show and (obj is self.window or obj.parent() is self.window):
                annotate_controls(obj)
            elif kind == QEvent.Type.Enter and self.enabled:
                self.detail = None
                widget = obj
                while widget and not widget.toolTip():
                    widget = widget.parentWidget()
                if widget:
                    self.target = weakref.ref(widget)
                    self.timer.start()
            elif kind in {QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.Wheel}:
                self.timer.stop()
                self.detail = None
                QToolTip.hideText()
        return False

    def table_detail(self, widget, position):
        table = widget
        while table is not None and not isinstance(table, QTableView):
            table = table.parentWidget()
        if table is None or not self.window.isAncestorOf(table) or not table.property("itemHoverDetails"):
            return None
        header = table.horizontalHeader()
        if widget is header or header.isAncestorOf(widget):
            column = header.logicalIndexAt(header.mapFromGlobal(position))
            item = table.horizontalHeaderItem(column) if column >= 0 else None
            return ("header", column, item.toolTip()) if item else None
        if widget is table.viewport() or table.viewport().isAncestorOf(widget):
            index = table.indexAt(table.viewport().mapFromGlobal(position))
            item = table.item(index.row(), index.column()) if index.isValid() else None
            return ("cell", index.row(), index.column(), item.toolTip() or item.text()) if item else ("empty", "")
        return None

    def show_pending(self):
        widget = self.target() if self.target else None
        if not self.enabled or widget is None or not shiboken6.isValid(widget) or not widget.isVisible():
            return
        hovered = QApplication.widgetAt(QCursor.pos())
        if hovered is None or (hovered is not widget and not widget.isAncestorOf(hovered)):
            return
        text = self.detail[-1] if self.detail else " ".join(widget.toolTip().split())
        if self.detail and self.table_detail(widget, QCursor.pos()) != self.detail:
            return
        if not text:
            return
        QToolTip.showText(QCursor.pos() + QPoint(12, 18), text, widget, QRect(), 5000)
