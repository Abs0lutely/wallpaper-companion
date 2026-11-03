# Windows EXE、便携 ZIP 与安装版

普通使用者从 [Releases](https://github.com/Abs0lutely/wallpaper-companion/releases) 下载，无需 Python、Conda 或 Inno Setup。

- `WallpaperCompanion-<版本>-windows-x64-portable.zip`：解压整个文件夹，运行 `WallpaperCompanion.exe`。不要只复制 EXE；`_internal` 是必需的动态运行库。`portable.flag` 使配置/音频留在同目录 `data/`，插件位于 `plugins/`。请解压到有写权限的位置。
- `WallpaperCompanion-<版本>-windows-x64-setup.exe`：当前用户安装，无需管理员权限，默认 `%LOCALAPPDATA%\Programs\WallpaperCompanion`。配置在 `%LOCALAPPDATA%\WallpaperCompanion`，插件在其 `plugins/`；共享资源默认在安装目录 `shared/`。升级/卸载保留配置、用户创建的 shared 资源和外部资源；仅清理指向本次安装的自启项。
- `SHA256SUMS.txt`：上述两个文件的 SHA256。

支持 Windows 10/11 x64；不含 Wallpaper Engine、GPT-SoVITS 模型、参考音频、个人语音或音乐。ffprobe 仍可通过界面配置，未捆绑独立 ffprobe。云服务由用户填写接口和凭据。

## 自行构建

应用图标统一取自 `readme-assets/app-icon.ico`（用户参考图生成的粉发樱花耳机少女，九档 16–256px），母版为同目录 `app-icon.png`。需要重建 ICO 时运行 `.\.conda\python.exe scripts/prepare_app_icon.py`，只缩放编码，不重新绘图。构建阶段复制该 ICO 到 `build/app.ico`，供 EXE 和 Inno Setup 共用；运行中的窗口、托盘从 readme-assets 读取同一份资源。更换图标后必须完整冻结，不使用 `--skip-freeze`；本地源码替换不会更新已安装 EXE。生成提示词与来源说明见 [图标设计记录](readme-assets/app-icon-design.md)。

v0.10.0 分发 `examples/audio/` 中 90 条用户授权的默认 WAV（52 条操作回应、38 条陪伴示例），无模型或个人配置。`build_windows.py` 在冻结前检查操作动作覆盖、WAV 格式、非全零内容及总清单 SHA256；实际发行 EXE 再次检查。26 类操作每类至少一条可用即可分发，缺失变体如实记录；当前全部默认配音完整。准备/追加素材用 `scripts/prepare_default_audio.py --source <生成目录> --apply`，详见[语音包说明](examples/audio/operation-voice/README.md)。个人 data/shared 音频仍不打包，只有清单内副本位于公开 examples 中。

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


本地开发新增中日各 90 条默认音频（总计 180），日本语音按白名单复制并保留原件。`validate_bundled_manifest` 检查全部文件与哈希；中日默认文本与资源分类保持对应。新独立声音模式不需要安装 WE。仅在正式发布阶段更新版本并构建，不因日常提交制作发行包。


### 陪伴包目录（本地开发中）

未来构建在冻结前调用 `companion.pack_builtins.validate_builtin_catalog()`，核对两包各 38 + 52 条现有获准录音。随整个 `examples/` 携带 `examples/packs/catalog.json`，无需在仓库重复保存音频 ZIP。随附 `COMPANION_PACKS.md` / `.en.md`。本轮未执行构建、安装或发行包验收；版本不升级。


### v0.11.0 正式分发验收

实际 EXE 自检还验证中日两包（各 38 陪伴 + 52 操作）、180 条资源 SHA256、无需 WE 的独立方案、F8/定时调度和导出再导入另一份隔离配置。此检查在云端对便携版及安装版各执行一次，不调用真实 TTS。用户个人数据及现有服务不参与验收。

## v0.12 自动更新发行门槛

构建会额外生成独立 `WallpaperCompanionUpdater.exe`，与 `app-version.txt` 一同随安装版和便携版分发。辅助程序被复制到用户数据更新暂存目录后运行，不占用待替换的程序目录。便携 CLI 与辅助程序复用 `companion/program_update.py`，原 `scripts/update_portable.py` 入口保留。

正式 GitHub Release 在现有安装/卸载验证后，再分别下载并校验 v0.11.0、v0.12.0 的真实历史安装包和便携包，由 `scripts/verify_upgrades.py` 在一次性 Windows runner 中执行两种升级、重启 EXE 自检、安装目录和数据哈希检查。此脚本拒绝在普通本地环境执行；不会为验证操作个人安装。验证不通过就不发布。两组升级串行执行，报告分别保存在 `output/upgrade-verification/<基线版本>/`，随 `release-verification` Actions artifact 保留。

本地备用构建仍执行原实际包验证；真实历史升级门槛属于正式云端发布流程。更新文件大小和 SHA256 来自同一 GitHub Release，并非独立数字签名；不提供代码签名证书，也不承诺取消 SmartScreen 提示。
