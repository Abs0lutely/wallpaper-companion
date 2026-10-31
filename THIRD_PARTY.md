# 复用组件与来源

本程序的配置、规则匹配和独立伴随逻辑是为本需求编写的连接代码。窗口、音频解码、全局输入捕获、HTTP 和进程检测复用成熟组件，没有复制整个壁纸引擎或角色框架。

| 组件 | 用途 | 上游与许可 |
|---|---|---|
| PySide6 / Qt 6.10.0 | 原生界面、托盘、QMediaPlayer 双通道播放、音量、暂停 | https://code.qt.io/pyside/pyside-setup.git/ ，LGPLv3/GPLv3/商业许可；详见所安装包的许可证 |
| pynput 1.8.1 | 鼠标和键盘 Listener、HotKey 组合键状态处理 | https://github.com/moses-palmer/pynput ，LGPLv3 |
| requests 2.32.5 | 连接本机 GPT-SoVITS HTTP API | https://github.com/psf/requests ，Apache-2.0 |
| psutil 7.1.2 | 只在 WE 已运行时查询当前壁纸，避免查询导致启动 WE | https://github.com/giampaolo/psutil ，BSD-3-Clause |
| keyring 25.6.0 | 系统凭据管理器保存 API 密钥 | https://github.com/jaraco/keyring ，MIT |

接口与实现参考：

- Qt 官方 QMediaPlayer 示例：https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QMediaPlayer.html
- Qt 官方 QAudioOutput：https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QAudioOutput.html
- pynput 官方鼠标 Listener 示例：https://pynput.readthedocs.io/en/latest/mouse.html
- pynput 官方 HotKey / canonical 示例：https://pynput.readthedocs.io/en/latest/keyboard.html
- WE 官方 `getWallpaper` 命令：https://help.wallpaperengine.io/en/functionality/cli.html#get-current-wallpaper
- GPT-SoVITS `POST /tts` 请求字段：https://github.com/RVC-Boss/GPT-SoVITS/blob/main/api_v2.py
- 本地 API 启动方式参考用户已有 MCP bridge 的启动流程；路径改为界面填写，日志存入本程序目录。
- 微软 Azure Speech REST：https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech
- OpenAI 兼容 Speech 协议：https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create
- 视频音轨检测使用外部 FFmpeg/ffprobe（PATH 自动发现或界面指定，不随源码包捆绑）：https://ffmpeg.org/ffprobe.html
- PKGV 目录结构参考 RePKG 的公开格式读取实现，仅独立读取文件索引，不解包： https://github.com/notscuffed/repkg/blob/master/RePKG.Application/Package/PackageReader.cs
- Windows 用户登录启动项依据：https://learn.microsoft.com/windows/win32/setupapi/run-and-runonce-registry-keys

前期调研中的 spine-particle-wallpaper、Touhou_Pet、wallpaper-engine-api 没有作为运行依赖或复制源码。当前壁纸查询直接采用官方接口。

Qt 自带的 FFmpeg 与传递依赖包含额外许可证；本地使用依赖环境保持原包内容。如果后续打包发布，应一并分发所需许可证、版权说明及 LGPL 所要求的材料。
