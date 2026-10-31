# 项目维护交接

此文件描述可公开的源码状态，不包含开发者本机配置和路径。

## 项目与架构

Windows 独立 Wallpaper Engine 音频伴随程序，Python 3.11+、PySide6、pynput、requests、psutil、keyring。应用版本 0.6.1；没有 SQL 数据库，使用本机 JSON 和系统凭据存储。

当前进入下一大版本的本地开发阶段：用户明确要求逐项实现、验证并本地提交，暂不推送 GitHub、不构建或发布 Release，不替换现用个人版。正式发布时才恢复既定 GitHub 工作流。版本号尚未提升。

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
- `companion/managed_api.py`：按需启动及等待 GPT-SoVITS，只记录并清理声伴自建的进程树；`providers.gpt_sovits` 在实际合成前接入，`ui.cleanup` 设置取消并清理 API。已有外部服务只复用，不终止。
- `companion/resources_ui.py`、`assets.channel_resources`：语音/BGM/台词分别选择直接共享、专用或保留旧路径。默认共享 `Store.path.parent/audio/shared`，默认专用 `audio/<配置ID>`，自定义专用根记录在 profile.private_asset_dir。切换不移动文件。
- `companion/audio_library.py`、`audio_library_ui.py`：共享和各壁纸目录去重清单、搜索/范围、真实试听、复制导入/分类目录、直接引用目标目录、Qt 系统回收站；不永久删除，不自动重写旧绑定。

长期规则见 `AGENTS.md`，使用方式及所有控件说明见 `README.md`、`USER_GUIDE.md`，扩展接口见 `EXTENSIONS.md`。

## 已完成

当前壁纸绑定；鼠标/键盘/随机时段/每日固定时刻语音；游戏式按键录制；38 条默认台词及编辑、导入导出、分类生成；BGM 独立暂停、实时音量、压低；库扫描与批量添加/移除；共享或独立资源目录；原音频证据与防冲突策略；三类 TTS 适配及自定义扩展；托盘、自启开关和帮助；可分享互动 JSON。

删除配置保留全部资源。预设不包含音频、模型、密钥、绝对路径、壁纸绑定或可执行插件。源码仓库不携带环境、用户数据或模型；Release 提供内置 Python/Qt 运行库的便携 ZIP、当前用户安装 setup.exe、SHA256SUMS。

v0.6 的便携版以 portable.flag 识别，数据在 EXE 旁 data/；安装版数据在用户 LOCALAPPDATA/WallpaperCompanion，升级/卸载保留。自启命令适配 EXE，不再指向 main.py。原项目本机数据未迁移或覆盖。

## 数据关系

默认 `data/config.json`，可由 `WALLPAPER_COMPANION_DATA` 改变位置。配置默认版本 4；旧配置按缺省字段兼容，不代表完整迁移。

- 顶层包含路径、后端、显示器、轮询间隔、profiles、manual_profile、tts_provider/tts_providers、enabled_plugins。
- 新增可选 shared_asset_dir（空值使用当前 Store 的 data/audio/shared）；profile 新增可选 private_asset_dir（空值使用 data/audio/配置ID）。旧音频路径保持原样，配置版本仍为 4，新增字段按缺省值兼容。
- profile 包含 id/name/wallpaper、voice_dir/bgm_dir、asset_dir/dialogue_file、播放参数、dialogues 和 rules。
- rule 包含 id/name/enabled/event/hotkey/source/keyword、start/end、cooldown、随机 interval_min/max，固定时间另有 at。
- dialogue 包含 id/category/text/enabled。manual_profile 引用 profile.id；多个 profile 可以共享相同的资源和台词文件。
- 完整资源根含 voice/、bgm/、dialogues.json。并非所有旧配置均使用外部台词文件。
- 凭据保存在 keyring；冷却、下次随机时间和每日已触发标记只在内存。

## 验证与边界

本轮大版本本地改动：69 项单元/模拟服务测试通过。新增生命周期测试用隔离的真实 Python HTTP 子进程验证首次合成启动、重复生成复用、加载中退出及父子进程回收、外部服务保留；没有启动真实 GPT-SoVITS 模型或使用个人参考/音频。原生音频库测试通过 13 项：混合资源模式、自定义专用根重开保留、共享文件去重、真实试听、分类导入、搜索、目录直接引用、真实回收站、原文件保留、新共享根不改旧绑定、浏览不启动 API 及退出调用清理。壁纸库、规则、内置帮助原生流程回归通过。已有 controls 原生测试首次受真实全屏前台状态干扰，固定模拟前台状态后播放器及资源流程通过。compileall、pip check 和 diff 检查通过。测试证据只在本机 output/，不提交。

整体界面重设计留待后续，当前新增功能沿用现有标签页和弹窗。主窗口关闭仍留在托盘；真正退出才清理自建 API。API 生成完成后保留到本次声伴退出，避免逐条反复加载；所有台词跳过时不启动。取消可阻止剩余合成与保存，但外部/云服务已接收的 HTTP 请求无法撤回，后台请求可能等待超时；不终止外部 API。正常退出清理已验证，强制结束进程或崩溃时的系统级子进程兜底尚未实现。

本地发行新增 `build_release.cmd` 和 `scripts/release_local.py`：补齐固定依赖、源码测试、完整构建、实际分发包验证，成功后才将该次三个文件移入 `dist/verified/<版本>/<本次编号>/`。每次独立日志/验证报告，失败不提升临时包，并用 Windows 文件锁阻止重复双击并行运行；无 Git 或个人版更新操作。底层构建新增 `--release-dir`，验证新增 `--report-dir`，原命令默认行为保持兼容。普通 Markdown 发布指南为 `RELEASE_GUIDE.md`，已取代 Word 使用方式；不把本机路径写进公共指南。

此入口已实跑当前 0.6.1 完整构建与最终包验证，便携/安装 EXE 各 17 项检查、安装/卸载、用户数据保留及 SHA256 全部通过，未发布或替换个人版。新增 9 项编排测试覆盖缺依赖/编译器、源码/构建/验证失败、缺失/失败报告和验证后文件被改动时拒绝输出；全部 57 项测试、compileall、pip check 通过。源码归档包含入口及 Markdown 指南；双击 CMD 的重复构建拒绝与失败退出已实测。未专门在全新机器验证 Conda 自动发现；无 Conda PATH 时仍需按指南首次准备。

v0.6.1 修复手册按钮依赖外部 Markdown 打开方式且失败无反馈的问题，改为内置阅读窗口。源码手册按钮、导航、重开及缺文件报错流程已验证；48 项单元/模拟协议测试、五组原生界面流程、compileall、pip check 通过。最终便携和安装版 EXE 各通过 17 项自检，包含内置手册加载和文档跳转。

最新更新约定见 AGENTS/BUILDING：日常小改动本地验证并 commit 后只推送代码，不逐项发版；新增大功能仍须先获准再推送。正式发布默认采用“本地测试 → 修改版本并 commit、推送 → Windows checks 通过 → 手动启动 Windows release → 云端构建、验证并自动发布 Release”，不重复本地制作发行包；双击入口保留为特别要求本地打包/手动上传时的备用。此默认流程约定本身不触发一次发布。个人版单独更新，只换程序，不覆盖 data、配置/绑定/台词/音频、用户插件或迁移记录。用户仍编辑时只暂存，不强制退出，也不替换运行中 EXE。更新器测试覆盖拒绝用户数据覆盖、校验、运行中阻止、保留自定义文件和失败回滚。

已在隔离目录用真实 v0.6.0 便携 ZIP 升级到 v0.6.1：新 EXE 和内置手册正常，原程序备份校验正确，测试用户文件逐字节未变。证据为本机 output/upgrade-verification.json；不得把隔离验证写成已替换某位用户正在运行的个人版。

v0.6 的 42 项单元/模拟协议测试、五组原生界面流程、compileall 和 pip check 已通过。最终便携 ZIP、安装后 EXE 各通过 15 项自检；移除 Python/Conda/Qt 环境和 PATH，测试中文/空格路径、安装/卸载、用户数据保留及 SHA256 均通过。具体命令见 README/BUILDING。协议测试访问 loopback mock；受限环境可能需要允许本机连接。证据位于本机 output/release-verification.json，不随源码或 Release 上传。

曾发现并修复 Conda 构建错误收集 ICU 导致 QtCore ImportError：Qt 6.10 Windows wheel 使用 Windows 自带无版本后缀 ICU API，Conda ICU 78 使用不同导出。spec 排除冲突 DLL，必须继续用实际 EXE 测试，不能只看冻结命令返回成功。悬停测试也曾被未排空的窗口原生 Leave 事件打断；测试现等待窗口曝光和事件稳定，保留真实定时器断言，重新通过，产品提示逻辑未更改。

Azure 等真实付费账户合成、真实登录自启未作为上述测试实测完成。曾验证本地 GPT-SoVITS 和原生输入，但服务与模型由用户自行配置。

只读回退识别受 WE 保存配置延迟影响，不是精确渲染/暂停 API。原音频检测是文件/音轨证据，不是实时听声；未知情况下默认保守阻止 BGM。当前不是多个屏幕各自独立声道。插件是显式启用的 Python 代码，不是沙箱。

## 待处理与优先级

本轮后续优先：按用户反馈重整整体 UI，并在正式发布前验证真实本地 GPT-SoVITS 模型的按需启动/生成/退出、旧配置兼容与自定义共享/专用目录回归。任何真实模型验证应避免影响已运行的外部服务，不得用真实个人资源做删除或故障注入。

1. 用隔离 Store 做保存失败故障注入：`ui.save_profile` 先写共享台词再保存配置；`library.apply_bindings`、`presets.import_payload` 会先创建资源；`ui.save_tts` 先写 keyring。单文件原子替换不等于跨资源事务，失败可能留下部分变更。风险由代码审查发现，尚未故障注入复现。
2. 补充本机配置结构/版本兼容校验；验证无系统托盘时的关窗退出路径，避免隐藏进程。
3. 明确不同时间窗能否复用按键，统一编辑器重复按键限制与预设导入策略。
4. 按需实测云账户、真实登录自启、更多 WE 类型；完善生成取消和诊断。
5. 可选代码签名、更多架构、规则优先级/队列、含音频资源包。EXE、ZIP 和安装包构建已经实现，不再列为未实现功能。

已知调度边界：同分钟重启可能重复每日规则；错过时刻不补播。没有 TTS 中途取消；共享文件按需刷新而非监听。

下一次开发先检查 Git 状态，阅读 AGENTS，再从优先级 1 的隔离失败测试开始；禁止用真实用户配置做故障注入。
