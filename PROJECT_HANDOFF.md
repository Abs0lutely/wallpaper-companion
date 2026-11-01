# 项目维护交接

此文件描述可公开的源码状态，不包含开发者本机配置和路径。

## 当前本地迭代：自动保存与操作语音（未推送）

本轮按较大的功能更新处理，用户明确要求每项本地验证、提交，暂不推送、不发布、不打包。唯一功能 worktree 的当前分支为 `feature/companion-experience`，从已发布 main/v0.8.2 `10c6586` 创建；main、UI worktree 和旧的台词预设分支未合并或修改，版本号仍为 0.8.2，正式发布时再提升版本。已安装程序及个人配置/音频保持原样；不把此前发布/清理的一次性授权用于本轮。

已实现并分项提交：

- `3f04766`，`companion/audio_library_ui.py`：未选音频时打开首个可见文件目录；显式全选/全不选和 Ctrl/Shift 多选；“删除”仍确认后进入回收站，不降级永久删除，批量复制/删除作用于选中记录。
- `583c2b7`，`companion/library_ui.py`：生成勾选独立于保存的台词元数据，首次打开/切换库不自动勾选，支持全部/清空/按分类选择；重绘同库保留本次选择。编辑弹窗不再混入持久的“参与生成”开关。
- `52d27e2`，`companion/rules_ui.py`：分类改为不可手写的下拉，来自当前台词分类和语音目录的一层子目录；保留旧规则缺失的分类，自选文件/文件夹继续可用。
- `173f266`，`companion/ui.py`：参考音频直接播放与停止；GPT-SoVITS 相对路径按项目根解析，不调用 API。
- `e0125a4`，`companion/autosave.py`、UI/库模块：离开页面/内页、切换配置、关闭到托盘与正常退出前保存配置、规则、台词及接口/运行/目录设置。约 6.5 秒的非模态弹窗带撤销按钮，设置另有持久撤销入口。撤销只改本次差异，关联共享台词按原字节及配置引用一起恢复；新草稿、后续配置保存或外部文件变化阻止覆盖。失败保留草稿并阻止导航，保留原手动保存入口。密钥仍在 keyring，不参与撤销。恢复默认经确认，保留绑定、资源、台词、角色和接口，不操作系统自启。
- `119d805`，`companion/shell_ui.py`：关闭 BGM 即保存并隐藏底部播放器，重新开启恢复；读取 Qt 歌曲 CoverArtImage/ThumbnailImage，或同目录 cover/folder.jpg/png，缺失显示默认图标，不用自定义窗口背景冒充歌曲封面。
- `0076996`，`companion/action_lines.py`、`operation_voices.py`、`operation_pack.py`：26 类共 52 条原创操作台词、默认开启的操作语音开关及可选目录；按按钮语义、页面切换、实际编辑等事件播放预制音频，无 TTS 调用。控件更新不当成用户输入，修改提示合并、快速操作节流，已有语音/暂停/全屏时不抢播。后台扫描按自定义、当前配置、共享、随程序语音包逐类回退。缺失时设置显示覆盖数，不伪造声音。
- `c751b7b` 及后续回归：自动保存不重启当前音乐、不清空未改动规则的时钟；选择器同步、失败内页导航阻止、相对参考音频、接口保存回退、异步操作音频刷新均有回归。

新增配置为 `operation_voice_enabled: bool = true`、`operation_voice_dir: str = ""`，在原 version 4 JSON 中向后兼容，Store 校验类型；无 SQL 数据库。操作语音不通过互动预设导出，也不携带密钥。页面单步撤销不包含文件删除、系统自启、原实时音量和手动保存等独立即时动作。

验证：101 项隔离单元/协议测试、17 组原生 UI 流程、28 项源码自检通过，compileall、pip check、diff check 通过；新增 `tests/smoke_autosave.py`、`smoke_player_art.py`、`smoke_operation_voices.py` 和 `test_operation_pack.py` 纳入 `scripts/validate_ui.py`。撤销测试覆盖外部文件改动、新草稿阻止、共享引用恢复、临时 Store 写入失败；操作语音通过非零测试 WAV 实际进入 QMediaPlayer PlayingState，不是语音内容/音质听评。封面测试为 Qt 元数据传递模拟和实际本地 sidecar 图片读取，尚未验证各格式真实内嵌封面的解码兼容性。本轮未调用用户 9880、未切换模型、未真实生成 GPU 配音、未构建二进制。

**下一步须用户先生成真实音频，不能直接发布：**

1. 使用 `examples/dialogues/operation-zh-CN.json`，按分类生成全部 52 条 16-bit WAV，保留分类和按台词命名的文件名；TXT 仅供阅读，不保留分类。现有 38/72 条陪伴台词保留，新增操作台词单独提供，可在软件按钮中去重导入。
2. 用户提供生成目录后，听评并确认可公开分发；用 `scripts/prepare_operation_voice_pack.py --source <目录>` 校验，随后加 `--apply` 只复制这 52 条到 `examples/audio/operation-voice`，不收集个人其他音频/模型，不覆盖已有不同内容。该目录当前仅说明文件，没有正式音频。
3. `scripts/build_windows.py` 已在冻结前用 `require_pack` 阻止缺失/无效/全零音频，冻结 EXE 自检再次检查完整性；现有 examples 分发与便携更新白名单会携带该包。保持此门槛，不用测试 WAV 凑数。以后获用户授权再提升版本、验证、合入 main、推送并运行工作流。
4. 原壁纸音频检测按用户要求留待后续讨论，本轮未修改其检测策略或实现。此前的默认配音、真实多格式封面和新发行包均不能写成已实测。

## v0.8.2 发布准备：API 控制、操作反馈与按钮动效

用户随后明确授权推送并打包分发。本轮发布版本为 0.8.2；分支 `feature/api-controls-feedback` 从已发布 main `201bb5d` 创建，四项提交截至 `bb81ca7`，独立于尚未推送的 `content/heartfelt-rules`。按默认流程合入 main，Windows checks 通过后手动启动 Windows release；不提前建标签，不本地重复构建，不替换现用安装文件或用户数据。发布是否成功以对应 Actions/Release 为准。

- 首项提交 `9df4ffb`：新增手动启动/关闭自建 API；仅回收本程序创建的进程树，关闭后可重启。外部服务只连接，不关闭或在启动动作中切换模型；加载/生成期间禁用冲突操作。检测冷服务改为可操作的提示，不直接显示 HTTPConnectionPool 堆栈。保存接口和切换生成目录都有明确结果。
- 第二项提交 `9db235b`：`feedback.py` 统一操作短提示与底部反馈，区分操作已接收和最终结果，覆盖动态 Qt 对话框并处理 C++ 内部按钮的包装对象生命周期。`speech_ui.py`、services 的可选 status 回调和 Qt 信号显示实际保存/跳过条数、当前阶段、等待动画和阶段输出；不会伪造模型内部百分比，失败保留部分结果。开始生成会把进度区域滚入视图。
- `motion.py`：复用 Qt QPropertyAnimation/OutBack，90ms 轻压、360ms 回弹，只缩放绘制内容，不改控件几何/点击区域。支持中途连击、键盘触发、禁用回正、隐藏/失活停止和动态对话框按钮；静止时关闭图形效果，不维持空闲动画。不替换第三方按钮已有的图形效果，系统原生文件选择器不受影响。
- 全部 99 项隔离单元/协议测试、14 组原生流程通过；API 启停为临时假 API 进程，生成使用假语音后端。另有 12 项 API 按钮检查、8 项生成/反馈检查、11 项动画检查；角色、配置、共享库、音频和窗口/托盘闪烁回归通过。补验服务在空闲时自行退出的情形：点击仍显示的“关闭”只清理旧状态，不能意外变成启动。未在本轮启动/关闭用户真实 9880 或实测 GPU 模型启动，不能把模拟结果当作真实合成验证。

发布前再次完成全部 99 项单元/协议测试、14 组隔离原生流程、compileall、pip check。发行 EXE 自检新增 API 控件、部分生成进度保留及按钮动效/反馈模块加载检查，源码自检 27 项通过；没有启动或切换用户真实语音服务。云端将对本次实际便携包与安装包重复自检和卸载数据保留验证。

## v0.8.1 小版本修复

分支 `fix/v0.8.1-dialogue-library` 从 v0.8.0 main 创建，用户已授权测试后推送和发布。本轮不卸载、删除或迁移现用安装版及其个人数据；v0.8.0 的一次性清理已经完成，不能重复执行。

- 根因：无配置时 `ui.select_profile(-1)` 清空台词，补充/导入等动作又因 `editing_id` 为空直接返回。现由 `library_ui.DialogueMixin` 加载共享默认台词，不必先绑定壁纸即可补充、编辑、保存、导入导出及分类生成；操作有明确反馈。初次仅展示默认值，用户保存才写 JSON；损坏文件不会被静默覆盖。创建首个绑定或更换共享根目录前保存共享草稿，写入失败阻止切换。
- `runtime.Layout.shared_dir`、`assets.shared_root`：实际安装版/便携版默认程序目录 `shared`，配置仍在原数据目录；临时 Store 与显式 WALLPAPER_COMPANION_DATA 使用隔离数据目录下 shared。批量绑定接入同一默认解析，不移动旧路径或音频。`.gitignore` 排除 shared。
- 安装器不分发用户 shared 数据，卸载保留用户创建的 shared；更新器同样保护 shared。实际安装/卸载验证新增 shared 保留检查；EXE 自检增加无绑定台词恢复/保存和默认共享位置，避免只验证已有配置。
- README 已重写并附三张真实演示截图。`scripts/capture_readme.py` 在临时配置下可重建图片；发行包包含 readme-assets，便携更新器识别其为程序文档资源。
- `examples/dialogues/heartfelt-zh-CN.json` / TXT 为 72 条原创中文台词，六类各 12 条，单独提交。JSON 保留分类、重复导入去重；v0.8.0 可先新建配置导入。正式工作流额外提供这两个独立附件，同时仍保留三个主程序发行文件；主程序 SHA256SUMS 仍校验 ZIP 和安装包。

验证：96 项隔离单元测试、十一组原生界面流程通过；新增首次启动流程 14 项，包括实际 72 条台词包导入去重、无绑定模拟分类生成、共享草稿保护和坏 JSON 不覆盖。源码自检 24 项、compileall、pip check 通过。未调用用户 9880、未生成这批台词的真实音频；云端实际便携/安装版验证结果以对应 v0.8.1 工作流为准。

## v0.8.0 整合状态

用户已明确授权合并、推送并正式发布。整合分支 `integrate/v0.8.0` 从原 main 创建，依次通过 Git 合并功能分支 `92d1438` 与 UI 分支 `d247382`，保留双方历史。UI worktree 仅有已知的本地 AGENTS.md 隔离规则修改，已备份并原样保留，没有混入发布提交。

`companion/core.py` 的冲突保留角色与外观两组校验；`companion/ui.py` 同时组合 CharacterMixin 和 CompanionShellMixin，退出同时停止角色扫描、保存待提交播放器音量并停止其定时器。自动合并后另核对新版导航、角色表单、配置保存、动态提供方字段和资源绑定；保存角色不会丢失外观或壁纸绑定。

本地验证通过：95 项单元/模拟协议测试、10 组原生界面流程；加强后的角色流程共 15 项检查，源码版打包自检 21 项通过，compileall、pip check 和 diff 检查通过。所有测试使用 worktree 内隔离 Store 与资源审计；原 data 哈希未变。`scripts/validate_ui.py` 已纳入角色流程和角色模型路径审计。`companion/diagnostics.py` 新增新版导航、模型控件、YAML 依赖及配置共存检查，云端实际发行包验证将复用这些检查。

合并版语音回归使用模拟 API，未调用或切换用户独立启动的 9880 服务。下文神里绫华实机记录发生于合并前的功能分支，不作为合并版重复实测。云服务鉴权、其他角色/跨版本真实切换及人工音质听评仍未验证。正式包仅由 GitHub 构建，在 Windows checks 与实际分发包验证通过后自动发布；最终结果以对应 Actions/Release 为准，不提前宣称发布成功。

v0.8.0 当次授权的个人便携版/数据及旧发行包清理已经完成，不是后续任务的持续删除许可。普通升级/卸载仍默认保留数据；两个开发 worktree、分支及独立 AI 项目保留。本机安装包从验证通过的 Release 下载并校验，没有重新构建。

## GPT-SoVITS 角色与模型选择实现

- `companion/characters.py`：只读扫描模型及参考音频，按名称、目录、版本提示生成唯一配对候选；角色预设增删改、字段白名单校验和同名原文读取。不读取权重内容，不猜测参考原文。自动配对不等于验证模型兼容性。
- `companion/characters_ui.py`、`companion/ui.py`：角色保存/另存为/选择/删除、模型下拉及浏览、项目扫描和参考音频选择。扫描在后台执行，保存、扫描和切换角色不启动 API；修改角色字段后切换有放弃确认。
- `companion/core.py`：JSON 新增 `tts_characters`（id/name/settings 列表）和 `tts_character`（当前角色 ID），保留配置版本 4 并对旧配置提供默认值。角色记录包含项目、Python、两项模型、参考音频、原文、两种语言和语速；API 地址及外部切换许可属于接口设置，不随角色切换。
- `companion/sovits_config.py`、`companion/managed_api.py`：生成时才启动并加载所选模型；在数据目录 `tts-runtime/` 创建私有 YAML，不改 AI 项目原配置。同模型复用自建 API，模型改变时回收旧自建服务再启动；退出回收自建进程树与临时配置。外部服务不会被关闭，只有显式布尔许可为 true 才允许切换其全局模型；加载失败不发合成请求。模型加载与合成串行化，批量内复用同一模型。
- `companion/providers.py`、`companion/services.py`、`companion/extensions.py`：模型字段、布尔开关和批量快照接入现有提供方接口。角色不随共享互动 JSON 导出；删除角色只删元数据。
- `README.md`、`USER_GUIDE.md`、`EXTENSIONS.md`、`companion/help_ui.py`：补充模型、角色、外部服务和控件说明。新增依赖 PyYAML 6.0.3，已同步依赖清单和发行许可证收集代码；本轮未执行打包。

验证：隔离数据下 87 项单元/模拟协议测试通过；外部模型切换许可收紧后，相关 5 项再次通过（包含字符串/数字许可拒绝）。`tests/smoke_characters.py` 在 Qt offscreen 环境下 13 项流程检查通过，覆盖扫描不启动、完整角色保存恢复、模拟生成按台词命名及删除保留文件；`tests/smoke_polling_flicker.py` 的 11 项定时器/托盘回归通过。`pip check` 通过。首次受限环境完整回归曾在测试 HTTP 服务处超时，改用允许本机回环的验证环境后通过；真实语音服务未参与测试。原 data 中音频等 39 个资源文件哈希保持一致；验证期间检测到运行配置的 hover_help 字段改变及 app.lock 移除，用户已确认由其操作并退出原程序造成，保留当前设置未回滚，详情仅记录在本机隔离验证报告中。

2026-10-31 已完成一次用户授权的真实神里绫华中文 v4 验证：Qt offscreen 控件驱动角色保存/重新选择，从实际生成入口启动 GPU 推理；独立动态端口 59450，配置和输出均在独立测试目录。扫描、保存、选角色时无 API 进程，点击生成后才启动；日志确认加载所选 GPT/SoVITS 权重。生成 7.6 秒、48 kHz、单声道 16-bit 非静音 WAV，按台词命名；总验证耗时约 47 秒。参考原文采用原参考文件名已有标注，未自行猜写或经 ASR 校对。通过软件实际退出动作回收自建 API 及子进程，端口释放、私有 YAML 清除；原用户 data、AI 项目原配置、模型及参考音频哈希均不变，12 项实机检查全部通过。测试前未发现其他运行的 api_v2 服务，本轮未启动或切换共享接口。详细日志、报告和音频保留在本机忽略目录 `output/ayaka-live-20261031-01/`，不上传模型、音频或本机配置。

尚未验证：其他真实角色和跨版本切换、人工听评音质，以及新的二进制发行包。后续实机合成仍需独立端口和测试输出目录，不影响已有服务。UI 分支整合需要显式合并并重新验证，不能复制覆盖两个 worktree 的共享文件。

## 项目与架构

Windows 独立 Wallpaper Engine 音频伴随程序，Python 3.11+、PySide6、pynput、requests、psutil、keyring、PyYAML。源码版本 0.8.2；没有 SQL 数据库，使用本机 JSON 和系统凭据存储。

用户已本地试用本轮功能通过，并授权在“建立专用音频目录”增加二次确认、本地验证后推送 GitHub，启动工作流发布 v0.7.0。只在 GitHub 构建，不重复本地打包；不替换现用个人版。开发仓库 data 下的音频/BGM 已由用户明确声明可用于测试，授权不涉及旧项目或个人便携版数据。

v0.7.0 已通过 GitHub 工作流发布。其后修复用户反馈的整个窗口周期性闪烁、托盘时影响其他全屏应用的问题：原自动检测每次调用 WE GUI 的 getWallpaper（默认 4 秒），即使 stdout 为空也不断启动进程；现改为自动只读 selectedwallpapers，只有“立即检测”单次尝试官方命令。外部后台工具统一 SW_HIDE、CREATE_NO_WINDOW、STARTF_FORCEOFFFEEDBACK，保留冻结 DLL/环境清理。隐藏窗口暂停状态文字更新，恢复时同步，前台相同文字不重复写入。识别仍受 WE 保存延迟影响，没有更改 WE 或工坊文件。用户已重启实测确认不再闪烁，并明确授权推送、启动 GitHub 工作流发布 v0.7.1；不更新个人便携版，不重复本地打包。发布结果以对应 Release / Actions 记录为准。

本地闪烁修复验证：73 项测试通过（新增自动多轮不启动 GUI、配置更新/屏幕选择、损坏配置不启动进程、手动命令保留和后台启动参数检查）。`tests/smoke_polling_flicker.py` 用真实 Qt 定时器/窗口、模拟全屏前台状态与查询进程验证 11 项：前台无重复状态写入、隐藏无 Show/Paint/状态重写、后台绑定继续跟随、恢复同步、手动查询一次且临时标记不持久化。播放器/保存切换、controls、内置帮助原生流程回归通过，compileall/pip check/diff 检查通过。用户另在自己的使用环境确认修复有效；旧 v0.7.0 EXE 不含此修复，新 EXE 须由 v0.7.1 工作流构建验证。

专用目录流程现为：选择模式并保存 → 查看配置名及实际路径的二次确认（默认否）→ 确认后才创建/保存。`tests/smoke_resource_confirmation.py` 实测真实 QMessageBox 是/否按钮；设置弹窗取消或二次取消均保留配置字节且不创建目录，确认后创建并保存，原共享文件保留，7 项检查通过。全部 69 项单元/模拟协议测试、compileall、pip check 通过；GitHub 最终包验证结果以对应 Actions 运行记录为准。

- `main.py`：Qt 入口、单实例锁、托盘启动。
- `companion/ui.py`：界面、活动配置匹配、后台任务编排。
- `companion/core.py`：配置 Store、路径保护、时间/事件规则和音频文件选择。
- `companion/audio.py`：独立语音/BGM 播放、压低、暂停及音量。
- `companion/services.py`、`companion/paths.py`：壁纸默认只读配置轮询、显式手动命令查询、输入和系统集成。
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
- `companion/resources_ui.py`、`assets.channel_resources`：语音/BGM/台词分别选择直接共享、专用或保留旧路径。默认共享 `程序目录 shared（隔离 Store 使用其数据目录下 shared）`，默认专用 `audio/<配置ID>`，自定义专用根记录在 profile.private_asset_dir。切换不移动文件。
- `companion/audio_library.py`、`audio_library_ui.py`：共享和各壁纸目录去重清单、搜索/范围、真实试听、复制导入/分类目录、直接引用目标目录、Qt 系统回收站；不永久删除，不自动重写旧绑定。

长期规则见 `AGENTS.md`，使用方式及所有控件说明见 `README.md`、`USER_GUIDE.md`，扩展接口见 `EXTENSIONS.md`。

## 已完成

当前壁纸绑定；鼠标/键盘/随机时段/每日固定时刻语音；游戏式按键录制；38 条默认台词及编辑、导入导出、分类生成；BGM 独立暂停、实时音量、压低；库扫描与批量添加/移除；共享或独立资源目录；原音频证据与防冲突策略；三类 TTS 适配及自定义扩展；托盘、自启开关和帮助；可分享互动 JSON。

删除配置保留全部资源。预设不包含音频、模型、密钥、绝对路径、壁纸绑定或可执行插件。源码仓库不携带环境、用户数据或模型；Release 提供内置 Python/Qt 运行库的便携 ZIP、当前用户安装 setup.exe、SHA256SUMS。

v0.6 的便携版以 portable.flag 识别，数据在 EXE 旁 data/；安装版数据在用户 LOCALAPPDATA/WallpaperCompanion，升级/卸载保留。自启命令适配 EXE，不再指向 main.py。原项目本机数据未迁移或覆盖。

## 数据关系

默认 `data/config.json`，可由 `WALLPAPER_COMPANION_DATA` 改变位置。配置默认版本 4；旧配置按缺省字段兼容，不代表完整迁移。

- 顶层包含路径、后端、显示器、轮询间隔、profiles、manual_profile、tts_provider/tts_providers、enabled_plugins。
- 新增可选 shared_asset_dir（空值使用当前 Store 的 程序目录的 shared）；profile 新增可选 private_asset_dir（空值使用 data/audio/配置ID）。旧音频路径保持原样，配置版本仍为 4，新增字段按缺省值兼容。
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

后续开发优先处理下列已知边界。UI 与角色功能已整合，旧配置、共享/专用资源和角色共存回归已通过；合并前真实神里绫华按需启动/生成/退出验证另有记录，不能泛化为所有角色已实测。任何真实模型验证应避免影响已运行的外部服务，不得用真实个人资源做删除或故障注入。

1. 用隔离 Store 做保存失败故障注入：`ui.save_profile` 先写共享台词再保存配置；`library.apply_bindings`、`presets.import_payload` 会先创建资源；`ui.save_tts` 先写 keyring。单文件原子替换不等于跨资源事务，失败可能留下部分变更。风险由代码审查发现，尚未故障注入复现。
2. 补充本机配置结构/版本兼容校验；验证无系统托盘时的关窗退出路径，避免隐藏进程。
3. 明确不同时间窗能否复用按键，统一编辑器重复按键限制与预设导入策略。
4. 按需实测云账户、真实登录自启、更多 WE 类型；完善生成取消和诊断。
5. 可选代码签名、更多架构、规则优先级/队列、含音频资源包。EXE、ZIP 和安装包构建已经实现，不再列为未实现功能。

已知调度边界：同分钟重启可能重复每日规则；错过时刻不补播。没有 TTS 中途取消；共享文件按需刷新而非监听。

下一次开发先检查 Git 状态，阅读 AGENTS，再从优先级 1 的隔离失败测试开始；禁止用真实用户配置做故障注入。
