# 性能重构交接：关机前检查点

## 当前结论

实现、自动更新整合和功能回归已完成；**性能验收尚未全部完成**。剩余工作是使用不记录调用历史的模拟函数复核长时间内存趋势。用户因可能随时关机要求保存现场，本次不再启动新的长测。

用户已明确选择低常驻内存方案：约 67 MiB，不预热字体；接受首次开窗等待。最终五轮首次开窗中位数 2.39 秒，范围 2.13–3.08 秒；后续热重开中位数 63.6 ms。不要改为约 101 MiB 的字体预热方案，也不要省略首次开窗代价。

## 工作区与历史

- 当前可运行整合源码：`E:\AAA_ChatGPT\Github项目\wallpaper-companion-integrated`，分支 `integration/runtime-auto-update`，入口 `start.cmd`。
- 性能专用源码：`E:\AAA_ChatGPT\Github项目\wallpaper-companion-perf`，分支 `perf/runtime-efficiency`；从固定 `2055adf594949747f4ac47d5396311efd95eb0f2` 创建。
- 自动更新聊天已完成后才整合固定 `ea5bbe93aa1efa5de2f0ecd60dd2c5db66e8f165`。合并提交 `9c3977e` 保留双方历史；后续 `ce40a50` 优化真实托盘恢复入口，`d2b77fc` 改进首次/后续启动基准。
- 两个工作区各有独立 `.conda`。未推送、发布、打包或替换个人版，未操作现有语音服务。不要在其他聊天的工作区修改代码。

## 已完成证据

实测细节见 `docs/integration-report.md` 和相邻性能工作区 `docs/performance-report.md`，不要仅凭本交接中的摘要重新计算结论。

- 整合版 177 项单元测试、30 个原生界面流程通过。汇总 `output/verification-final.json`；逐项报告 `output/ui-validation/*.py.json`。`summary.json` 会被单项复测覆盖，不可用它误判全套数量。
- 最新托盘恢复改动已在两个工作区分别通过 `scripts/validate_ui.py --only smoke_runtime_efficiency.py`。标准与规格审查均完成，最后的小改动和测量口径另经只读复核。
- 五轮短测、十分钟常驻和两组完整三十分钟长测已保存。所有测试使用合成音频和隔离 Store；WE、输入状态、模型及更新网络使用模拟；Qt 播放器实际播放静音 WAV。
- 依赖清单：两侧 `output/performance/environment.json`，30 项包版本一致。
- 整合版关键数据：`output/performance/integrated-final-*`、`integrated-tray-access`、`integrated-reused-data`、`integrated-stream-stress`。
- 固定基线在性能工作区 `output/baseline-source`；原始数据在其 `output/performance`。不要用最近的 Git HEAD 代替基线，`SOURCE_REVISION` 固定为 `2055adf...`。

## 尚未解决的验收问题

落盘采样的三十分钟测试完成约 900 次实际配置交替和刷新。第 20–25 分钟与第 25–30 分钟私有内存中位数：基线 152.88 → 153.88 MiB；整合版 132.63 → 133.63 MiB。双方仍增加约 1 MiB，**不得写“无持续增长/全部验收通过”**。

分配追踪发现 `unittest.mock` 的调用历史在累积，尤其是频繁调用的前台状态和目录发现替身。这是已确认的测量污染来源，但还没有证明它解释全部增长。独立执行 6000 次 `QTimer.singleShot` 的探针没有复现回调保留，不能把原因归给定时器。

最新 `scripts/benchmark_runtime.py` 已把这些 Mock 替换为普通函数，并用无状态对象隔离语音服务；下一步必须用它重测。应用逻辑没有为此改动。

关机前短程检查 `constant-fakes-check` / `baseline-constant-fakes-check` 均已完成，进程退出码为 0；下一次不必重复这些检查，只需先核对报告与日志。两组新的三十分钟任务尚未启动。

临时分配追踪探针在 50 ms 触发周期下发生 `processEvents()` 重入与 IndexPending 超时；其数据仅用于找分配来源，不能作为功能/稳定性通过依据。探针与日志保留在 `output/performance/probes` 和 `output/performance/allocation-retention-probe`。

## 下次继续步骤

1. 先读本文件、项目 `AGENTS.md` 与两个报告；检查两个 worktree 的 Git 状态，不切换别人的分支。所有必要提交都在本地。
2. 检查短程 `constant-fakes-check` 与 `baseline-constant-fakes-check` 是否通过，查看 JSON 的 `errors` 和日志中的 `Traceback`。缺少时只补这些短测。
3. 把整合版当前 `scripts/benchmark_runtime.py` 复制到性能工作区的 `output/baseline-source/scripts/benchmark_runtime.py`，保持双方脚本完全相同。
4. 使用下面命令各运行一组 1800 秒长测。可并行，但记录机器存在其他负载；不要启动或停止个人应用来制造空闲环境。
5. 比较后两个五分钟窗口、逐分钟趋势和日志。若仍持续增长，继续定位，不能把相对基线更低当作稳定性通过。必要时先缩短/加速诊断；加速压力回调需防止 `processEvents()` 导致重入。
6. 用同样的无历史替身补充 600 秒托盘常驻；更新报告生成器，加入新标签并保留旧数据及其污染说明。检查源码逐文件哈希，区分实机 Qt 行为与外部服务模拟。
7. 更新 Archify 候选及 HTML 的待验收状态，再做本地提交。只有最后指标达标才宣布完成；本轮仍不推送/发布。

整合工作区（PowerShell）：

```powershell
.\.conda\python.exe scripts/benchmark_runtime.py --label final-clean-stress --items 1000 --rounds 1 --seconds 1800 --stress --stream-metrics --switch-profiles --mode wallpaper_engine
.\.conda\python.exe scripts/benchmark_runtime.py --label final-clean-resident --items 100 --rounds 1 --seconds 600 --tray --resident --stream-metrics
```

固定基线目录 `E:\AAA_ChatGPT\Github项目\wallpaper-companion-perf\output\baseline-source`：

```powershell
& '..\..\.conda\python.exe' scripts/benchmark_runtime.py --label baseline-final-clean-stress --items 1000 --rounds 1 --seconds 1800 --stress --stream-metrics --switch-profiles --mode wallpaper_engine
& '..\..\.conda\python.exe' scripts/benchmark_runtime.py --label baseline-final-clean-resident --items 100 --rounds 1 --seconds 600 --tray --resident --stream-metrics
```

现有报告生成命令（在性能工作区；尚未自动纳入上面的新标签）：

```powershell
.\.conda\python.exe scripts/summarize_performance.py --integrated-root ../wallpaper-companion-integrated
```

## 建议技能

继续使用 `diagnosing-bugs` 定位剩余趋势，按需使用 `codebase-design`；实质性代码变更后使用 `code-review`。更新可视化说明使用 `archify`。无需重新访谈或重新实施已完成模块。

## 关机安全

源码、报告和交接写入 Git；大型原始数据与独立环境因 `.gitignore` 不进 Git，但已落在上述工作区磁盘中，正常关机不会丢失。再次交接前确认测试命令已退出。本次不留下新的三十分钟任务，也不需要任何服务继续运行。
