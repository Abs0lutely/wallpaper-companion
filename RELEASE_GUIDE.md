# 壁纸声伴：版本打包与发布指南

以发布 **v0.7.0** 为例；实际版本以 `pyproject.toml` 为准。平时小改动只验证、提交源码，不必制作发行包。正式发布默认采用 GitHub 工作流；只有特别要求本地打包、手动上传时，才使用第二节备用流程。

## 一、默认流程：GitHub 构建、验证并自动发布

1. 完成功能开发，先在本机验证相关实际流程，并运行单元测试、compileall 和 pip check。
2. 修改 `pyproject.toml` 的 `[project] version`，例如 `0.7.0`；这次版本修改也要提交。
3. 本地 commit，推送待发布代码到 `main`。到 Actions 确认该提交的 **Windows checks** 通过。
4. 进入仓库 **Actions → Windows release**。若停用，点击 **Enable workflow**。
5. 点击 **Run workflow**，分支选 `main`，tag 输入与版本对应的 `v0.7.0`，启动运行。默认不要提前单独创建或推送这个标签，避免重复触发。
6. 等待本次运行成功：云端会安装构建依赖、运行测试、制作便携 ZIP 和安装包、验证真实 EXE 及安装卸载，最后自动创建公开 Release。
7. 到 Releases 确认版本和三个附件：portable.zip、setup.exe、SHA256SUMS.txt；按需完善更新说明，下载并核对校验值。

**启动 Windows release 就是在启动正式发布，而不只是试打包。** 新版本使用未发布过的版本号；若对应 Release 已存在，当前工作流保留其原附件，不自动替换。测试失败时先修复并重新验证，不手动发布失败产物。

这条默认路线无需在本机双击打包，也无需手动上传附件或暂停自动工作流。GitHub 工作流不会更新你电脑上的个人版，个人版按第四节另行安全更新。

本机源码检查示例（项目根目录，已准备好环境）：

```powershell
.\.conda\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.conda\python.exe -m compileall -q companion main.py scripts
.\.conda\python.exe -m pip check
```

## 二、备用流程：本地双击打包与手动发布

### 1. 完成功能并设置版本号

在维护源码的项目目录操作，不要在个人免安装版或旧项目中构建。先实际体验本次功能，确认保存、播放等操作正常，整理更新说明。

编辑项目根目录 `pyproject.toml`：

```toml
[project]
version = "0.7.0"
```

文件中不加 `v`，GitHub 标签使用 `v0.7.0`。构建脚本自动读取版本，无需手动改 EXE、ZIP、安装包文件名。已经正式发布的版本不要重复使用。

### 2. 双击打包与验证

双击项目根目录的 **`build_release.cmd`**。不需要手动打开终端，也不需要管理员权限。

脚本按顺序执行：

1. 使用项目 `.conda\python.exe`；不存在时调用 `setup.ps1` 创建环境（首次需要系统能找到 Conda）。
2. 检查固定版本依赖，缺少时安装 `requirements-build.txt`；检查依赖一致性。
3. 执行全部单元测试及源码编译检查。
4. 缺少 Inno Setup 时，从官方来源下载固定版本并校验 SHA256。
5. 完整冻结 Python/Qt，生成临时便携 ZIP、setup 安装包和校验文件。
6. 对本次临时包校验 SHA256，在带中文、空格的隔离目录运行真实便携 EXE 自检，再静默安装、自检安装版、卸载，核对测试数据保留。
7. 全部通过后，将本次三个文件移到 `dist\verified\<版本>\<本次编号>\`，并自动打开该目录。

EXE 验证必须先有临时包，因此第 5 步会先构建；**只有第 6 步通过才会产生本次的 verified 最终目录**。失败立即停止并保留日志，不能把临时包当成已验证发行包。成功不代表本次新功能已经全部手动体验，仍需完成第 1 步。

测试期间可能短暂出现窗口和低音量测试音；不调用真实 TTS、不写密钥、不开启自启。不要同时运行旧的手动构建命令。双击入口自身会防止重复并行构建。

脚本不执行 Git 提交、推送、创建标签、发布 Release，也不退出或替换你的个人版，不访问个人音频库。关闭脚本窗口会中断流程；请等待成功或失败后再按任意键关闭。

### 3. 取出验证通过的三个文件

只使用本次成功窗口显示、自动打开的目录。例如：

```text
dist/verified/0.7.0/<本次编号>/
  WallpaperCompanion-0.7.0-windows-x64-portable.zip
  WallpaperCompanion-0.7.0-windows-x64-setup.exe
  SHA256SUMS.txt
```

- `portable.zip`：提供给别人完整解压运行；不要只分发 EXE，`_internal` 运行库也是必需的。
- `setup.exe`：当前用户安装，无需管理员权限。
- `SHA256SUMS.txt`：这两个文件的 SHA256。

每次运行创建独立编号，旧的成功目录不会删除或覆盖。失败后不要误拿之前的成功目录发布本次代码。日志与自检报告在 `output\local-release\<本次编号>\`，不上传 GitHub；可能含本机路径。`dist\.release-staging\` 为未通过最终门槛的临时产物，也不上传。

### 4. 手动提交与推送代码

在项目根目录打开 PowerShell，先检查要提交的内容：

```powershell
git status --short
git add .
git diff --cached --stat
git commit -m "release: prepare v0.7.0"
git push -u origin main
```

已经提交过全部修改时，跳过 commit。不要提交配置、音频、模型或密钥；`.conda/`、`data/`、`dist/`、`build/`、`output/` 已被忽略。程序发行包作为 Release 附件上传，不加入 Git 历史。

到 GitHub 的 Actions 页面确认该次提交的 Windows checks 通过。若合并远端带来代码变化，应重新打包验证后再发布。

### 5. 手动创建 GitHub Release

如果希望完全使用本机生成的附件，先暂停自动发行工作流，防止创建 `v*` 标签时重复打包（普通源码检查仍保留）：

```powershell
gh workflow disable release.yml --repo Abs0lutely/wallpaper-companion
```

然后打开 [项目 Releases 页面](https://github.com/Abs0lutely/wallpaper-companion/releases)：

1. 点击 **Draft a new release**。
2. 创建标签 `v0.7.0`，Target 选择包含本版代码的 `main`。
3. 填写版本标题、更新说明与实际验证范围。
4. 上传第 3 步**本次 verified 目录里的三个文件**，等待上传完成。
5. 保存为草稿，核对版本、标签及附件；正式版不勾选 Pre-release。
6. 确认后点击 **Publish release**。

代码推送和发布附件是两个操作，双击脚本均不会代替你执行。希望恢复自动打包时手动运行：

```powershell
gh workflow enable release.yml --repo Abs0lutely/wallpaper-companion
```

### 6. 检查公开下载

从刚发布的 Release 重新下载两个包与校验文件，到下载目录检查：

```powershell
Get-FileHash .\WallpaperCompanion-0.7.0-windows-x64-portable.zip -Algorithm SHA256
Get-FileHash .\WallpaperCompanion-0.7.0-windows-x64-setup.exe -Algorithm SHA256
```

结果应和 `SHA256SUMS.txt` 相同。GitHub 自动附带的 Source code ZIP 是源码，不能代替 portable.zip。

## 三、首次准备

安装 Miniconda/Anaconda。若双击时找不到 Conda，在 Anaconda/Miniconda PowerShell Prompt 进入克隆后的项目目录，运行一次 `setup.cmd`。环境准备好后再次双击 `build_release.cmd`。

首次缺少工具时需要访问 Python 包索引和 GitHub。以后依赖已匹配、Inno 已存在时跳过安装和下载。

手动推送需要安装 Git；使用 `gh` 命令还需要 GitHub CLI，并完成：

```powershell
gh auth login
gh auth setup-git
```

### 本机旧仓库的首次历史同步（仅适用于尚未同步的旧副本）

早期此项目通过 API 上传过源码，本机旧仓库与远端曾出现内容一致、提交历史不相连的情况。新克隆的仓库不用执行本节。只有确认仍属于该旧状态时，先提交保存修改、确认工作区干净，再备份并合并一次：

```powershell
git branch backup-before-manual-sync
git fetch origin main
git merge --allow-unrelated-histories --no-edit origin/main
```

这不是日常拉取命令。若出现冲突，处理后重新验证，不能强制推送覆盖远端。

## 四、个人版数据与可选更新

打包脚本不会更新个人版。免安装版数据在 EXE 旁 `data/`；安装版数据在 `%LOCALAPPDATA%\WallpaperCompanion`，正常升级和卸载保留数据。两种使用方式的数据不会自动互相迁移。

需要更新现有个人免安装版时，使用已有更新器，不要覆盖整个目录：

```powershell
$target = "你的个人免安装版完整目录"
$zip = "本次verified目录里的portable.zip完整路径"
$sha = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
.\.conda\python.exe scripts\update_portable.py --target $target --archive $zip --sha256 $sha
```

更新器先返回 `plan.json` 路径，只暂存程序。保存各页面配置并从系统托盘退出旧程序后执行：

```powershell
$plan = "实际返回的plan.json完整路径"
.\.conda\python.exe scripts\update_portable.py --target $target --plan $plan --apply
```

仅替换程序，备份旧程序并比较用户文件哈希；保留配置、壁纸绑定、台词、音频、个人插件和迁移记录。运行中拒绝替换，不强制结束编辑实例。移动已有个人目录后，原配置的绝对音频路径可能需要重新选择。

## 五、常见报错（主要针对备用本地流程）

| 表现 | 处理 |
| --- | --- |
| 找不到 Conda / `.conda\python.exe` | 在 Anaconda/Miniconda Prompt 中先运行 `setup.cmd`，再双击。 |
| 依赖安装或工具下载失败 | 看本次 `build.log` 和终端错误，恢复网络后重试；不跳过 SHA256 校验。 |
| 没有 PyInstaller / Qt DLL 加载失败 | 确认使用项目环境与最新构建脚本，补齐 `requirements-build.txt` 后完整重建；不要手工混入其他环境 DLL。 |
| Another local build is running | 等另一个双击构建结束。锁随进程退出自动释放，不必删除锁文件；旧的手动脚本不参与此锁。 |
| 文件占用 / Access denied | 退出 `dist\WallpaperCompanion` 中的试运行 EXE，检查目录权限后重试；不要强制退出仍在编辑的个人版。 |
| A real installation exists | 验证保护了当前正式安装。在另一测试账号或虚拟机运行完整流程；不要卸载自己的正式环境来凑通过。 |
| 单元测试、EXE 自检或安装验证失败 | 查看本次日志及 `verification/` 下的报告、安装卸载日志。修复后重新运行；没有本次成功目录不能发布。 |
| FAILED / 没有打开最终目录 | 以前成功的目录可能仍在，但不代表本次通过。以本次窗口的 VERIFIED 路径和日志为准。 |
| nothing to commit | 内容已提交时直接 push，不用为了提交随便改文件。 |
| non fast forward | 提交本地修改，`git fetch origin` 后 `git merge origin/main`，解决冲突、重新验证再推送；不要直接 force push。 |
| 认证失败 / 443 连接失败 | 用 `git remote -v`、`gh auth status` 检查仓库与登录；连接错误先恢复网络，不能靠修改历史解决。 |
| 标签或 Release 已存在 | 尚未发布的草稿可继续编辑；正式发布后用新版本重新构建，不替换同版的不同程序内容。 |
| 创建 Release 又触发自动打包 | 先暂停 `release.yml`，见正常流程第 5 步。 |
| 安装版看不到便携版配置 | 两者数据目录不同，先检查旧数据并安排迁移，不表示数据已删除。 |
| 便携版不能启动 | 完整解压 ZIP，保留 `_internal` 与 `portable.flag`，不要只运行单个 EXE。 |

## 六、脚本与参考

- 双击入口：`build_release.cmd`；本地编排：`scripts/release_local.py`。
- 完整构建：`scripts/build_windows.py`；实际包验证：`scripts/verify_windows.py`。
- 底层手动构建说明：[BUILDING.md](BUILDING.md)；项目约定：[AGENTS.md](AGENTS.md)。
- [GitHub 官方 Release 操作说明](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub CLI 暂停工作流](https://cli.github.com/manual/gh_workflow_disable)

该指南取代原 Word 版；按下一版示例编写，不会自行提升当前软件版本。
