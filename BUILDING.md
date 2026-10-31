# Windows EXE、便携 ZIP 与安装版

普通使用者从 [Releases](https://github.com/Abs0lutely/wallpaper-companion/releases) 下载，无需 Python、Conda 或 Inno Setup。

- `WallpaperCompanion-<版本>-windows-x64-portable.zip`：解压整个文件夹，运行 `WallpaperCompanion.exe`。不要只复制 EXE；`_internal` 是必需的动态运行库。`portable.flag` 使配置/音频留在同目录 `data/`，插件位于 `plugins/`。请解压到有写权限的位置。
- `WallpaperCompanion-<版本>-windows-x64-setup.exe`：当前用户安装，无需管理员权限，默认 `%LOCALAPPDATA%\Programs\WallpaperCompanion`。用户数据在 `%LOCALAPPDATA%\WallpaperCompanion`，插件在其 `plugins/`。升级/卸载不删除用户数据或外部资源；仅清理指向本次安装的自启项。
- `SHA256SUMS.txt`：上述两个文件的 SHA256。

支持 Windows 10/11 x64；不含 Wallpaper Engine、GPT-SoVITS 模型、参考音频、个人语音或音乐。ffprobe 仍可通过界面配置，未捆绑独立 ffprobe。云服务由用户填写接口和凭据。

## 自行构建

**正式发布默认使用 GitHub 的 Windows release 工作流**，步骤见 [RELEASE_GUIDE.md](RELEASE_GUIDE.md)。本机只做相关测试，提交推送、等待 Windows checks 通过后，在 Actions 手动启动 Windows release；云端构建、验证通过后自动发布 Release，无需重复本地打包。

**本地构建备用入口：双击项目根目录 `build_release.cmd`**。用于特别要求本地打包、手动上传时，自动检查/补齐依赖、运行源码测试、完整构建，并验证实际便携 EXE 和安装/卸载。只有全部通过才将本次三个发行文件放进 `dist/verified/<版本>/<本次编号>/` 并打开该目录；失败保留日志在 `output/local-release/<本次编号>/`，不生成本次已验证目录。脚本不操作 Git/GitHub，也不更新个人版。首次需要能发现 Conda，或先在 Anaconda Prompt 运行 setup.cmd。

以下是底层手动命令（输出 `dist/release/`，需自己确认验证通过；不要与双击脚本并行运行）：

在 Windows x64、Python 3.11 的项目环境执行（源码安装方式见 README）：

```powershell
python -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_inno.ps1
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/build_windows.py
python scripts/verify_windows.py
```

也可 `python scripts/build_windows.py --iscc <已有的ISCC.exe>`。固定 PyInstaller 版本见 requirements-build.txt。bootstrap 固定官方 Inno Setup 6.7.4 并校验 SHA256，以便携方式放在 build/tools，不修改全局工具安装。

产物位于 `dist/release/`。源码/文档变更后应重新构建；`--skip-freeze` 只用于运行代码完全未变的文档调整。build/dist/output 受 Git 忽略。复制源码包或克隆仓库不会携带本机环境或数据。

`packaging/wallpaper-companion.spec` 使用 onedir 动态库布局，保留可替换 Qt DLL；`packaging/installer.iss` 生成当前用户安装包和卸载程序。依赖许可及对应源码位置见 THIRD_PARTY.md 和安装目录 licenses/。未使用签名证书，产物未数字签名；SHA256 用于核对下载完整性。

## 打包验证

正式发布前在源码 worktree 用 `.\.conda\python.exe scripts/validate_ui.py` 完成隔离回归，覆盖新版界面、角色预设、配置共存、规则、音频及资源目录；测试使用临时模拟服务，拒绝连接真实 9880。云端后续验证实际 EXE 时会额外检查新版导航、模型选择控件和配置字段。

verify_windows.py 从 ZIP 解压到带中文和空格的隔离目录，使用只含 Windows 系统目录的 PATH、移除 Python/Conda/Qt 环境变量，执行真实 EXE 自检；随后静默安装到另一个隔离目录、执行安装后 EXE、自卸载，核对数据保留。

EXE 的 `--self-test <报告路径>` 仅供构建验证：临时配置、低音量 WAV、双播放器/压低/暂停、界面保存、规则预设、凭据后端发现、输入监听器和扩展示例。不会调用 TTS、写密钥或开启自启。测试窗口可短暂出现，不发送系统快捷键。详细结果保留在本机 output/，不作为 Release 附件，以免上传本机路径。

安装验证先检查是否已有正式安装；如存在则拒绝运行，避免改动既有安装。仅验证安装/注册/卸载流程，不是完整登录后自启实测。不同机器/系统环境仍可能有差异。

## 自动发布

小功能和小修复先本地验证、commit，再直接推送代码；不逐项制作 EXE、ZIP、setup.exe，不自动更新 Release 或个人免安装版。新增大功能先本地完成、验证、commit，取得用户允许后再推送。只有进入获准的二进制发布阶段，才统一打包、验证实际 EXE/安装流程并同步 Release 和个人版。不能将未经验证的改动直接推送发布。

个人便携版更新使用 `scripts/update_portable.py`，默认只暂存，不会关闭程序：

```powershell
python scripts/update_portable.py --target <个人免安装目录> --archive <新版portable.zip> --sha256 <SHA256SUMS中的值>
# 保存各页面配置，并从托盘退出旧程序后：
python scripts/update_portable.py --target <个人免安装目录> --plan <上一步返回的plan.json> --apply
```

更新仅替换白名单内的程序/运行库/随附说明，旧程序备份到 `.program-backups`，完整新库替换旧库。data、用户插件、迁移记录、其他自定义文件及 portable.flag 保留，应用更新前后比较其哈希；运行中拒绝替换，不强制退出，失败回退程序文件。不要用覆盖整个目录或删除重装的方式更新个人版。

`.github/workflows/release.yml` 只在手动运行或推送 `v*` 标签时打包：安装固定依赖 → 单元测试 → 冻结 → 生成 ZIP/setup → EXE 自检和安装/卸载 → 发布包含校验文件的 Release。普通代码推送只运行 Windows checks，不生成分发包。未获准发布时，不触发该工作流或创建发布标签。默认只打 Windows x64，版本必须匹配 pyproject.toml；只有全部验证通过才上传公开附件。
