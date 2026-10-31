# 项目维护交接

此文件描述可公开的源码状态，不包含开发者本机配置和路径。

## 项目与架构

Windows 独立 Wallpaper Engine 音频伴随程序，Python 3.11+、PySide6、pynput、requests、psutil、keyring。应用版本 0.5.0；没有 SQL 数据库，使用本机 JSON 和系统凭据存储。

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

长期规则见 `AGENTS.md`，使用方式及所有控件说明见 `README.md`、`USER_GUIDE.md`，扩展接口见 `EXTENSIONS.md`。

## 已完成

当前壁纸绑定；鼠标/键盘/随机时段/每日固定时刻语音；游戏式按键录制；38 条默认台词及编辑、导入导出、分类生成；BGM 独立暂停、实时音量、压低；库扫描与批量添加/移除；共享或独立资源目录；原音频证据与防冲突策略；三类 TTS 适配及自定义扩展；托盘、自启开关和帮助；可分享互动 JSON。

删除配置保留全部资源。预设不包含音频、模型、密钥、绝对路径、壁纸绑定或可执行插件。此仓库只分发源码，环境、用户数据、测试产物和模型由使用者自行提供。

## 数据关系

默认 `data/config.json`，可由 `WALLPAPER_COMPANION_DATA` 改变位置。配置默认版本 4；旧配置按缺省字段兼容，不代表完整迁移。

- 顶层包含路径、后端、显示器、轮询间隔、profiles、manual_profile、tts_provider/tts_providers、enabled_plugins。
- profile 包含 id/name/wallpaper、voice_dir/bgm_dir、asset_dir/dialogue_file、播放参数、dialogues 和 rules。
- rule 包含 id/name/enabled/event/hotkey/source/keyword、start/end、cooldown、随机 interval_min/max，固定时间另有 at。
- dialogue 包含 id/category/text/enabled。manual_profile 引用 profile.id；多个 profile 可以共享相同的资源和台词文件。
- 完整资源根含 voice/、bgm/、dialogues.json。并非所有旧配置均使用外部台词文件。
- 凭据保存在 keyring；冷却、下次随机时间和每日已触发标记只在内存。

## 验证与边界

公开整理前基线验证：36 项单元/模拟协议测试、五组原生 smoke 流程、compileall 和 pip check 通过。具体命令见 README。协议测试访问 loopback mock；受限环境可能需要允许本机连接。

Azure 等真实付费账户合成、真实登录自启未作为上述测试实测完成。曾验证本地 GPT-SoVITS 和原生输入，但服务与模型由用户自行配置。

只读回退识别受 WE 保存配置延迟影响，不是精确渲染/暂停 API。原音频检测是文件/音轨证据，不是实时听声；未知情况下默认保守阻止 BGM。当前不是多个屏幕各自独立声道。插件是显式启用的 Python 代码，不是沙箱。

## 待处理与优先级

1. 用隔离 Store 做保存失败故障注入：`ui.save_profile` 先写共享台词再保存配置；`library.apply_bindings`、`presets.import_payload` 会先创建资源；`ui.save_tts` 先写 keyring。单文件原子替换不等于跨资源事务，失败可能留下部分变更。风险由代码审查发现，尚未故障注入复现。
2. 补充本机配置结构/版本兼容校验；验证无系统托盘时的关窗退出路径，避免隐藏进程。
3. 明确不同时间窗能否复用按键，统一编辑器重复按键限制与预设导入策略。
4. 按需实测云账户、真实登录自启、更多 WE 类型；完善生成取消和诊断。
5. 可选独立 EXE、规则优先级/队列、含音频资源包。

已知调度边界：同分钟重启可能重复每日规则；错过时刻不补播。没有 TTS 中途取消；共享文件按需刷新而非监听。

下一次开发先检查 Git 状态，阅读 AGENTS，再从优先级 1 的隔离失败测试开始；禁止用真实用户配置做故障注入。
