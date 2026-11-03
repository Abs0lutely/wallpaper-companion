# v0.13.0 发布验收记录

状态：2026-11-03 正式发布完成，公开下载文件复核通过。

- Release：https://github.com/Abs0lutely/wallpaper-companion/releases/tag/v0.13.0
- 发行标签提交：`313963c955d8acc18859b2ef783d42a820c75964`。性能与自动更新历史完整保留，普通非强制推送到 main。
- Windows checks：https://github.com/Abs0lutely/wallpaper-companion/actions/runs/41655780689
- Windows release：https://github.com/Abs0lutely/wallpaper-companion/actions/runs/41656099635

## 已通过验证

- 云端 180 项单元测试、源码编译；本地新增发布辅助检查共 12 项、依赖检查及规范/规格两项独立审查通过。
- 实际便携和安装 EXE 自检、中文及空格路径、安装/卸载、配置与共享资源保留。
- v0.11.0 → v0.13.0、v0.12.0 → v0.13.0：两组按顺序执行；每组的便携版和安装版升级、独立冻结辅助程序交接、重启自检、用户数据/音频/插件/陪伴包哈希及安装位置检查均通过。
- 公开 Release 为正式非预发布版本，标签指向上述提交；18 个附件严格匹配现有白名单，没有测试日志。
- 从公开 Release 下载两个程序包，文件大小、SHA256SUMS.txt 与 GitHub asset digest 三方一致。

## 公开程序包 SHA256

| 文件 | 字节数 | SHA256 |
|---|---:|---|
| WallpaperCompanion-0.13.0-windows-x64-portable.zip | 111999036 | `112181c4ca923898d1f56beabbfc7504d5a15110b4d45ddba254185746adc8a8` |
| WallpaperCompanion-0.13.0-windows-x64-setup.exe | 91358006 | `9045a485ab403a008f85f506d273bfaa6de17f8ca209bd1c01eb8cd054d53202` |

## 诊断与验证边界

首轮发行 41654479004 在实际包自检被拦截，没有发布产物。原因是自检在尚未显示的延迟加载页面上检查按钮动效；隔离复现确认实际访问后动效与反馈正常。修正诊断流程以访问页面后检查目标按钮并恢复导航，原生动效流程 14 项检查通过，未修改产品启动或内存策略。修正后的完整发行门槛已重新通过，失败报告收集新增 frozen JSON。

本机性能结果与已接受的首次开窗取舍见 [稳定性报告](performance-stability.md) 和 [整合记录](integration-report.md)。性能数据使用合成资源与模拟外部服务；本次实际 EXE 与升级在一次性 Windows runner 验证，不代表真实 WE 或第三方合成服务实测。没有替换个人版或操作现有语音服务。

云端报告保存在成功发行运行的 release-verification artifact；本地原始日志、分版本报告、公开元数据、下载文件和 public-verification.json 位于忽略目录 output/release-v0.13.0/，不加入 Git。此验收记录为发行完成后的文档提交，不改变 v0.13.0 标签或已验证的程序包。
