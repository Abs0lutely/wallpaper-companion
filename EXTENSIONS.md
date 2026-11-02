# 扩展 API v1

扩展是可执行 Python，必须先由用户信任并显式启用。文件名限小写字母、数字、下划线，字母开头。禁用并重启后不执行；API 版本不匹配只记录错误。

## 最小事件扩展

```python
API_VERSION = 1

def register(registry):
    registry.register_event("my_event", "我的事件", poll)

def poll(config, now):
    return False
```

复制到 `plugins/my_extension.py`，启动使其出现在运行设置，勾选保存并重启。安装版使用 `%LOCALAPPDATA%\WallpaperCompanion\plugins`；源码/便携版使用程序旁的 plugins。以界面“打开扩展目录”按钮为准。EXE 只内置本程序和现有依赖；插件需要额外第三方库时，需维护者重新打包，或改用源码环境安装该依赖。

`poll` 在 GUI 线程每秒调用，应快速返回 bool，不做网络和阻塞操作；自行节流、去重。True 进入宿主规则、时段、冷却匹配。

## 语音提供方

参见 `examples/plugins/custom_http_tts.py`：

```python
from companion.extensions import Field, SpeechProvider

SpeechProvider(
    id="my_speech", title="我的服务",
    fields=[Field("url", "地址"), Field("api_key", "密钥", "password")],
    synthesize=synthesize,  # (settings, text) -> 完整 PCM WAV bytes
    check=check,            # (settings) -> 状态文字
    description="服务说明", start=None,
)
```

`Field` 支持 text/password/file/directory/multiline/float/bool，可设 default/help。bool 字段以复选框展示并保存为 JSON 布尔值。内置 GPT-SoVITS 还使用 gpt_model/sovits_model 构建可扫描的模型路径选择器。密码字段写入 OS 凭据管理器并从 JSON 移除；合成时以临时 settings 传给扩展，勿记入日志。

合成、检测、启动在工作线程执行。合成只返回 WAV，不自行写文件；宿主处理验证、命名、重名、壁纸目录保护。抛异常停止批次并保留先前文件。`request_audio` 提供 HTTPS、超时、禁止重定向；按服务协议改 payload 即可。

## 壁纸后端

`register_wallpaper(id, title, query)`：工作线程中的 `query(config)` 返回：

```python
{"path": "唯一壁纸路径或标识", "title": "显示标题", "running": True, "source": "来源"}
```

无壁纸返回空 path。不要修改软件文件、切换壁纸，或把历史记录当实时状态。绑定使用规范化 path 匹配。

## 输入后端

`register_input(id, title, factory)`，构造 `factory(emit)`。`emit(event_id, rule_id)` 可从工作线程调用，Qt Signal 转交主线程。普通事件 rule_id 空串，快捷键为规则 ID。

对象实现 `configure(rules)`、`start()`、`stop()`。回调不阻塞 OS 输入线程，不记录文本；输入事件经过宿主桌面范围、全屏与冷却过滤。

## 壁纸库扫描后端

`register_library(id, title, scan)`：`scan(config)` 在工作线程运行，返回 `{"records": [...], "warnings": [...]}`。每个 record 需要 `path`（实际存在的入口文件）、`title`、`type`、`project`、`workshop_id`、`directory`、`source` 字段。不要写入扫描目录。内置实现见 `companion/library.py`。

宿主负责搜索、勾选和批量绑定，不让扩展在扫描过程中自动修改用户配置。重复记录按入口路径去重；用户明确点击批量绑定后才写入声伴配置。附加目录在配置 `library_roots` 中，也加入写入保护。

## 播放后端

`register_audio(id, title, factory)`，构造 `factory(parent)` 返回 QObject，契约见 `companion/audio.py`：

- Signals：message(str)、changed()。
- 方法：set_profile(profile_or_none)、play_voice(path)、next_bgm()、set_paused(bool)、stop()。
- 属性：busy、last_bgm、voice_output（有 setVolume）、voice（有 stop）。后两项供界面试听使用。
- BGM 控制：set_bgm_paused(bool)、set_bgm_blocked(bool)、set_volumes()；属性 bgm_paused、bgm_blocked。手动暂停、防冲突暂停、全局暂停必须相互独立，避免恢复全局播放时取消用户的 BGM 暂停。

Qt 播放在 GUI 线程执行。宿主判断全屏/暂停，后端只控制自己的声音。

## 原壁纸音频检测

`register_audio_detector(id, title, detect)`，工作线程执行 `detect(config, wallpaper_path)`，返回 `{"state": "yes|no|possible|unknown", "detail": "判断依据"}`。只有确切的无音轨证据才能用 no；缺少工具/异常使用 unknown。不能把文件素材存在当作实时正在播放。宿主按配置策略决定是否只暂停伴随 BGM。

资源配置新增 asset_dir、dialogue_file。共享台词应通过 `companion.assets.load_dialogues` 读取，避免用配置中的旧文本副本覆盖已更新文件。批量删除绑定不得删除资源目录。

## 加载和错误

已加载后端在运行设置中选择，保存并重启。插件在注册表副本上注册，失败丢弃本次更改，不留下半个插件。ID 不得覆盖其他能力。加载/事件错误在运行记录显示。

## 贡献

互动配置分享格式为 `wallpaper-companion-preset` version 1，代码见 `companion/presets.py`。只允许播放设置、规则和台词白名单；来源必须是语音目录内相对路径，不接受绝对路径、URL 或上级目录。未知事件 ID 可保留，但未加载时禁用。切勿在分享配置中携带插件执行入口、API 参数或密钥。

固定时刻事件 ID 为 `scheduled`，字段 `at` 采用 HH:mm。键盘事件仍保存 pynput canonical 格式，前端录制只负责转换输入，不改变输入后端协议。

Fork 后新增扩展、添加本机 mock 协议测试、运行 README 中检查，再提 PR。说明字段、台词是否外发、返回格式与依赖。不要提交 data、环境、密钥、真实语音和模型。没有账户验证的云服务必须注明仅完成协议测试。


### 可编辑语言字段

语音提供方 `Field.kind="language"` 使用可编辑语言下拉框，保存 API 代码而非本地化标签。`companion/language_checks.py` 提供代码读取与保守文字特征检查；未知自填代码保持原样，不推断模型训练语言。已有 `text` 字段和扩展 API 版本不变。独立运行模式仅停用壁纸查询/扫描，不改变已启用的输入、播放和语音提供方扩展。
