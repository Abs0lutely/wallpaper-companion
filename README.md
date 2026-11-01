# 壁纸声伴 · Wallpaper Companion

给 Wallpaper Engine 的壁纸配上互动语音和文件夹 BGM：点击鼠标、按下快捷键，或在指定时段，听见一句回应。

独立运行的 Windows 桌面程序，**不修改 Wallpaper Engine 本体和已下载壁纸**，也不要求壁纸作者预先制作互动功能。

[下载 Windows 版](https://github.com/Abs0lutely/wallpaper-companion/releases/latest) · [完整使用手册](USER_GUIDE.md) · [72 条原创台词包](examples/dialogues/README.md) · [反馈问题](https://github.com/Abs0lutely/wallpaper-companion/issues)

![陪伴主页：声音设置、配置切换和底部播放器](readme-assets/home.png)

*截图均为程序真实界面，使用演示配置；不附带壁纸、角色模型或个人音频。*

## 可以做什么

v0.9.0 新增自动保存与撤销、独立操作回应规则、重复音频确认及播放器改进，并修复切换系统声音输出后仍使用旧设备的问题。随程序提供 90 条可直接播放的默认配音及 [52 条操作台词](examples/dialogues/operation-zh-CN.json)；新用户可先体验随附示例，再换成自己的音频。

| 功能 | 使用方式 |
|---|---|
| 每张壁纸有自己的声音 | 绑定语音和 BGM 文件夹；多张壁纸可以共享，也可以各用一套资源。 |
| 鼠标、键盘互动 | 按键、滚轮、录制快捷键或任意按键触发，支持冷却和时段限制。 |
| 按时间问候 | 早安、晚安、时段随机、每日固定时刻；支持跨午夜。 |
| BGM 播放器 | 暂停/继续、下一首、实时音量；说话时自动压低音乐。 |
| 壁纸库与音频库 | 批量扫描/绑定；搜索、试听、复制导入音频，删除绑定保留资源。 |
| 可编辑台词库 | 内置 38 条原创短句，无绑定也能编辑共享台词；支持 JSON/TXT。 |
| 本地与第三方 TTS | GPT-SoVITS 角色预设及模型选择、Azure Speech、OpenAI 兼容接口。 |
| 个性化与扩展 | 本地背景、自动取色、托盘；分享互动 JSON，注册第三方提供方与后端。 |
| 自动保存与撤销 | 切换页面/配置自动保存，短暂弹窗可撤销；手动保存仍保留，默认设置可恢复。 |
| 操作回应 | 默认开启，可关闭；独立规则可配置/导入导出，按操作播放已有配音，不因点击临时启动 AI。 |
| 模型音频命名 | 新生成文件按“台词-模型名称.wav”保存；自动推断或手填标签，旧音频兼容、不同模型分别查重。 |

## 下载与第一次使用

支持 **Windows 10/11 x64**。普通用户无需安装 Python 或 Conda。

1. 从 [Releases](https://github.com/Abs0lutely/wallpaper-companion/releases/latest) 下载 `*-setup.exe` 安装，或完整解压 `*-portable.zip` 后运行 `WallpaperCompanion.exe`。便携版保留 `_internal` 和 `portable.flag`。
2. 在 WE 播放壁纸，点击“立即检测 → 绑定当前壁纸”。也可通过“配置管理 → 新建配置”先试用。
3. 把真实语音放进 `shared/voice`，音乐放进 `shared/bgm`，或在“资源与绑定”选择已有目录。
4. 添加互动规则并保存。先用“随机试听语音”或“试听选中规则”检查播放，再回到桌面试用。

**台词文字不是音频。** 要听到声音，需自行导入音频，或使用语音服务生成 WAV。仅导入文字不会收费、启动模型或自动发声。

关闭窗口后留在托盘，从托盘菜单退出。登录自启默认关闭，可在“设置”中开启。顶部使用手册可直接在程序内阅读，开启“悬停说明”后停留约一秒可查看控件提示。

## 台词库：先写下想说的话

![台词库：分类、勾选生成、补充默认台词与导入导出](readme-assets/dialogues.png)

v0.8.1 起，尚未创建壁纸配置也能看到默认台词：

- 未选壁纸时，编辑共享台词，保存到 `shared/dialogues.json`；选择壁纸后编辑该配置的台词。
- “补充默认台词”只补缺少的条目，不覆盖自己的内容；已齐全时有提示。
- “按分类生成勾选台词”将 WAV 存入语音目录的分类子目录，默认跳过已有同名音频。

另提供 **《温柔回信》72 条原创中文台词**，六类各 12 条，偏温柔、煽情与日常安慰：

> 你不必带着好消息才回来，疲惫的你，也值得被好好欢迎。
>
> 今天没有完成的事情，不会把已经努力过的你变得一文不值。

[下载 JSON](https://github.com/Abs0lutely/wallpaper-companion/releases/latest/download/heartfelt-zh-CN.json) · [查看全部台词及说明](examples/dialogues/README.md)

导入：“台词库 → 导入台词 JSON / TXT → 选择 JSON → 保存台词库”。相同分类和文本自动去重。v0.8.0 用户先新建一个配置即可导入，不必先绑定实际壁纸。

## 互动规则：选择事件或时间

![互动规则：快捷键、鼠标回应和跨午夜随机语音](readme-assets/rules.png)

新建规则先选择事件或时间。事件分鼠标和键盘，快捷键可录制绑定；时间支持每日固定时刻和时段内随机播放。默认仅在桌面前台响应输入，可按配置调整。

播放来源留空时使用语音总目录，也可填写分类子目录或单个文件。通过冷却、关键词和生效时段减少打扰，语音不叠加。“应用分类触发规则”会填入 F8/中键回应及早晨/白天/夜间等规则；替换旧规则需要确认并保存。

## 资源放在哪里

共享资源默认在**程序安装目录或便携目录的 `shared` 文件夹**，而不是安装版的用户配置目录。安装在其他盘时，共享音频也跟随安装目录：

```text
WallpaperCompanion/
  WallpaperCompanion.exe
  shared/
    voice/             # 语音，可建早晨、夜间等分类子目录
    bgm/               # 背景音乐
    dialogues.json     # 保存后产生的共享台词
```

- 音频库可修改共享根目录；“资源与绑定”可分别选择语音、BGM、台词共享或专用。
- **已有绑定和自定义路径保持原样，不自动搬动旧音频。** 更改默认值不等于迁移。
- 安装版配置仍在 `%LOCALAPPDATA%/WallpaperCompanion`；便携版配置在程序旁 `data`。专用目录默认在配置数据目录的 `audio/<配置ID>`。
- 正常升级/卸载保留用户数据和用户创建的 `shared` 资源。安装包不包含个人音频，更新时也不应覆盖整个用户目录。

支持 WAV、MP3、OGG、FLAC、M4A、AAC、WMA、OPUS，实际解码取决于 Qt/FFmpeg。原壁纸音频采用证据检测与可选防冲突策略，不能保证识别所有场景的脚本音频。

## 通过本地或第三方接口生成语音

| 提供方 | 需要准备 |
|---|---|
| GPT-SoVITS | 本机项目、配套 `.ckpt`/`.pth`、参考音频及逐字原文；可保存角色预设。 |
| Azure Speech | 完整合成 endpoint、Key/密钥环境变量、voice ID、语言与语速。 |
| OpenAI 兼容 TTS | 完整 `/audio/speech` 地址，以及服务方要求的 Key、模型与音色。 |

GPT-SoVITS 扫描、选择和保存角色不加载模型；生成时自动启动自建 API，也可用“启动本地 API / 关闭自建 API”提前准备或回收服务。退出仍回收自建进程。外部 API 不会被关闭，切换其模型需单独许可；多人使用建议独立端口。

参考原文必须与参考音频逐字一致，不能填写待合成台词。密钥使用系统凭据管理器；第三方接口会收到待合成文本，并可能按账户计费。完整字段说明见 [使用手册](USER_GUIDE.md)。

## 分享与开发

互动 JSON 可包含规则、台词和播放参数，不携带音频、模型、密钥、绝对路径或插件代码。格式见 [互动示例](examples/interaction-preset.json)，扩展方式见 [EXTENSIONS.md](EXTENSIONS.md)。

源码运行需要 Python 3.11+，可使用本地 Conda：

```powershell
.\setup.ps1
.\.conda\python.exe main.py
# 或在准备好环境后双击 start.cmd
```

也可在自己的虚拟环境中执行 `python -m pip install -r requirements.txt` 后运行 `python main.py`。

```powershell
# 隔离配置、资源和模拟服务的完整回归
.\.conda\python.exe scripts\validate_ui.py
.\.conda\python.exe -m compileall -q companion main.py scripts
.\.conda\python.exe -m pip check
```

显式设置 `WALLPAPER_COMPANION_DATA` 或使用临时 Store 时，共享资源跟随隔离数据目录，避免测试写入真实安装目录。截图可用 `scripts/capture_readme.py` 从独立演示配置重新生成。

[构建说明](BUILDING.md) · [发布流程](RELEASE_GUIDE.md) · [维护交接](PROJECT_HANDOFF.md) · [依赖与许可](THIRD_PARTY.md)

正式发行由 GitHub 完成构建和实际 EXE/安装验证。不附带 Wallpaper Engine、AI 模型或第三方商业语音；互动以输入事件和时间规则为基础。
