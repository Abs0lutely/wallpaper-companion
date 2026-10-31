# 二进制分发许可证

程序代码采用项目根目录 LICENSE（MIT）。Qt/PySide6、pynput、FFmpeg 和 Python 等运行库具有各自许可证，并非全部适用项目 MIT。

本目录提供 LGPL/GPL 文本；构建时还会从已安装依赖元数据复制原始 LICENSE/COPYING/NOTICE，并加入 Python LICENSE。Qt 动态库置于 _internal 内，可用兼容版本替换；允许为调试修改后的 LGPL 库而进行必要的逆向工程。本项目不对这些许可权利施加限制。

构建使用未经修改的官方 PySide6 6.10.0 Windows wheel。对应应用源码和完整构建脚本位于 https://github.com/Abs0lutely/wallpaper-companion 。

上游对应源码：

- PySide/Shiboken 6.10.0：https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.0-src/ ，源码仓库 https://code.qt.io/pyside/pyside-setup.git/tag/?h=v6.10.0
- Qt 6.10.0 模块源码：https://download.qt.io/official_releases/qt/6.10/6.10.0/submodules/ ，包含 qtbase、qtdeclarative、qtmultimedia 和 qtshadertools 等实际动态依赖；源码未修改。
- Qt Multimedia 内附的 FFmpeg 构建配置和许可证：https://code.qt.io/qt/qtmultimedia.git/tree/src/3rdparty/ffmpeg?h=v6.10.0 ，FFmpeg 官方源码 https://ffmpeg.org/releases/ 。具体归属见 FFmpeg-attribution.json。
- pynput 1.8.1：https://github.com/moses-palmer/pynput/tree/v1.8.1
- Python：https://www.python.org/downloads/source/ ，版本见包内 Python-LICENSE.txt/实际构建环境。
- PyInstaller 引导器：https://github.com/pyinstaller/pyinstaller/tree/v6.22.3 ，其许可证含 Bootloader exception。

从上游取得并保持未修改的源码/运行库；分发者如替换版本，应同步更新许可证、对应源码和构建说明。完整第三方说明见根目录 THIRD_PARTY.md。
