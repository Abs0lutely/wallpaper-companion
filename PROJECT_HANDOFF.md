# 项目维护交接

此文件描述可公开的源码状态，不包含开发者本机配置和路径。

## 项目与架构

Windows 独立 Wallpaper Engine 音频伴随程序，Python 3.11+、PySide6、pynput、requests、psutil、keyring。应用版本 0.6.1；没有 SQL 数据库，使用本机 JSON 和系统凭据存储。

- `main.py`：Qt 入口、单实例锁、托盘启动。
- `companion/ui.py`：界面、活动配置匹配、后台任务编排。
- `companion/core.py`：配置 Store、路径保护、时间/事件规则和音频文件选择。
- `companion/audio.py`：独立语音/BGM 播放、压低、暂停及音量。
- `companion/services.py`、`companion/paths.py`：壁纸查询、只读配置回退、输入和系统集成。
- `companion/library.py`、`companion/library_ui.py`：只读发现壁纸、批量绑定/删除、台词编辑。
- `companion/assets.py`、`companion/dialogues.py`：独立/共享资源、默认台词。
- `companion/rules.py`、`companion/rules_ui.py`：分级规则编辑、按键录制和校验。
- `companion/presets.py`、`companion/presets_ui.py`：数据预设导入导出、预览。
- `companion/extensions.py`：插件 API v1 和动态表单注册契约。
- `companion/providers.py`、`companion/secrets.py`：GPT-SoVITS、Azure、OpenAI 兼容 TTS 及 keyring。
- `companion/original_audio.py`、`companion/startup.py`、`companion/help_ui.py`：原音频证据、可选登录自启、悬停帮助。
- `companion/runtime.py`：源码/便携/安装版目录布局；`companion/external.py`：冻结后启动外部 WE/ffprobe/SoVITS 时恢复子进程 DLL 查找并清理环境。
- `companion/diagnostics.py`：实际 EXE 的隔离自检；`scripts/build_windows.py`、`scripts/verify_windows.py`、`packaging/`：冻结、安装包及验证；详情见 BUILDING.md。
- `companion/documents_ui.py`：程序内 Markdown 手册与本地文档导航，避免依赖 Windows 文件关联；`scripts/update_portable.py`：仅暂存/替换程序、备份、用户文件哈希保护和失败回退。

长期规则见 `AGENTS.md`，使用方式及所有控件说明见 `README.md`、`USER_GUIDE.md`，扩展接口见 `EXTENSIONS.md`。

## 已完成

当前壁纸绑定；鼠标/键盘/随机时段/每日固定时刻语音；游戏式按键录制；38 条默认台词及编辑、导入导出、分类生成；BGM 独立暂停、实时音量、压低；库扫描与批量添加/移除；共享或独立资源目录；原音频证据与防冲突策略；三类 TTS 适配及自定义扩展；托盘、自启开关和帮助；可分享互动 JSON。

删除配置保留全部资源。预设不包含音频、模型、密钥、绝对路径、壁纸绑定或可执行插件。源码仓库不携带环境、用户数据或模型；Release 提供内置 Python/Qt 运行库的便携 ZIP、当前用户安装 setup.exe、SHA256SUMS。

v0.6 的便携版以 portable.flag 识别，数据在 EXE 旁 data/；安装版数据在用户 LOCALAPPDATA/WallpaperCompanion，升级/卸载保留。自启命令适配 EXE，不再指向 main.py。原项目本机数据未迁移或覆盖。

## 数据关系

默认 `data/config.json`，可由 `WALLPAPER_COMPANION_DATA` 改变位置。配置默认版本 4；旧配置按缺省字段兼容，不代表完整迁移。

- 顶层包含路径、后端、显示器、轮询间隔、profiles、manual_profile、tts_provider/tts_providers、enabled_plugins。
- profile 包含 id/name/wallpaper、voice_dir/bgm_dir、asset_dir/dialogue_file、播放参数、dialogues 和 rules。
- rule 包含 id/name/enabled/event/hotkey/source/keyword、start/end、cooldown、随机 interval_min/max，固定时间另有 at。
- dialogue 包含 id/category/text/enabled。manual_profile 引用 profile.id；多个 profile 可以共享相同的资源和台词文件。
- 完整资源根含 voice/、bgm/、dialogues.json。并非所有旧配置均使用外部台词文件。
- 凭据保存在 keyring；冷却、下次随机时间和每日已触发标记只在内存。

## 验证与边界

v0.6.1 修复手册按钮依赖外部 Markdown 打开方式且失败无反馈的问题，改为内置阅读窗口。源码手册按钮、导航、重开及缺文件报错流程已验证；48 项单元/模拟协议测试、五组原生界面流程、compileall、pip check 通过。最终便携和安装版 EXE 各通过 17 项自检，包含内置手册加载和文档跳转。

更新约定见 AGENTS/BUILDING：在此公开源码工作目录先验证、本地 commit，再验证发行包后同步 GitHub/Release。个人版只更新程序，不覆盖 data、配置/绑定/台词/音频、用户插件或迁移记录。用户仍编辑时只暂存，不强制退出，也不替换运行中 EXE。更新器测试覆盖拒绝用户数据覆盖、校验、运行中阻止、保留自定义文件和失败回滚。

已在隔离目录用真实 v0.6.0 便携 ZIP 升级到 v0.6.1：新 EXE 和内置手册正常，原程序备份校验正确，测试用户文件逐字节未变。证据为本机 output/upgrade-verification.json；不得把隔离验证写成已替换某位用户正在运行的个人版。

v0.6 的 42 项单元/模拟协议测试、五组原生界面流程、compileall 和 pip check 已通过。最终便携 ZIP、安装后 EXE 各通过 15 项自检；移除 Python/Conda/Qt 环境和 PATH，测试中文/空格路径、安装/卸载、用户数据保留及 SHA256 均通过。具体命令见 README/BUILDING。协议测试访问 loopback mock；受限环境可能需要允许本机连接。证据位于本机 output/release-verification.json，不随源码或 Release 上传。

曾发现并修复 Conda 构建错误收集 ICU 导致 QtCore ImportError：Qt 6.10 Windows wheel 使用 Windows 自带无版本后缀 ICU API，Conda ICU 78 使用不同导出。spec 排除冲突 DLL，必须继续用实际 EXE 测试，不能只看冻结命令返回成功。悬停测试也曾被未排空的窗口原生 Leave 事件打断；测试现等待窗口曝光和事件稳定，保留真实定时器断言，重新通过，产品提示逻辑未更改。

Azure 等真实付费账户合成、真实登录自启未作为上述测试实测完成。曾验证本地 GPT-SoVITS 和原生输入，但服务与模型由用户自行配置。

只读回退识别受 WE 保存配置延迟影响，不是精确渲染/暂停 API。原音频检测是文件/音轨证据，不是实时听声；未知情况下默认保守阻止 BGM。当前不是多个屏幕各自独立声道。插件是显式启用的 Python 代码，不是沙箱。

## 待处理与优先级

1. 用隔离 Store 做保存失败故障注入：`ui.save_profile` 先写共享台词再保存配置；`library.apply_bindings`、`presets.import_payload` 会先创建资源；`ui.save_tts` 先写 keyring。单文件原子替换不等于跨资源事务，失败可能留下部分变更。风险由代码审查发现，尚未故障注入复现。
2. 补充本机配置结构/版本兼容校验；验证无系统托盘时的关窗退出路径，避免隐藏进程。
3. 明确不同时间窗能否复用按键，统一编辑器重复按键限制与预设导入策略。
4. 按需实测云账户、真实登录自启、更多 WE 类型；完善生成取消和诊断。
5. 可选代码签名、更多架构、规则优先级/队列、含音频资源包。EXE、ZIP 和安装包构建已经实现，不再列为未实现功能。

已知调度边界：同分钟重启可能重复每日规则；错过时刻不补播。没有 TTS 中途取消；共享文件按需刷新而非监听。

下一次开发先检查 Git 状态，阅读 AGENTS，再从优先级 1 的隔离失败测试开始；禁止用真实用户配置做故障注入。
