"""Summarize retained raw measurements without treating missing runs as passes."""
import argparse
import json
from pathlib import Path
from statistics import median

MIB = 1024 * 1024


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(root, output, integrated=None):
    optimized = root / "output/performance"
    baseline = root / "output/baseline-source/output/performance"
    lines = ["# 运行性能重构实测报告", "",
             "**状态：本轮本地验收完成。** 最终无调用历史模拟函数的十分钟与三十分钟复核见 `docs/performance-stability.md`。下文保留历史轮次，含 Mock 的长测不作为稳定性证明。", "",
             "基线源码：`2055adf594949747f4ac47d5396311efd95eb0f2`。测量使用同一台 Windows 机器、独立复制的 Python 3.11 / PySide6 6.10 环境和合成资源。", "",
             "WE、系统输入和模型服务未接入真实个人环境；播放延迟使用真实 Qt 播放器与静音 WAV。结论针对源码运行，不代表冻结发行包、真实壁纸查询或 GPT-SoVITS 推理性能。", "",
             "启动时间包含创建测试进程、模块导入、Store 初始化和窗口/托盘运行层就绪，扣除合成夹具写盘时间；未包含真实输入钩子和单实例锁。短测每组五个新进程且各用新数据目录；另补充同一数据目录首次创建与后续复用的对照。没有清空操作系统文件缓存，不能称为磁盘冷启动。", "",
             "## 五轮短测", "", "下表为五轮中位数；内存为进程 Private Bytes，不是显存或 Python 对象大小。负变化表示减少。", "",
             "| 场景 | 基线启动 ms | 重构启动 ms | 变化 | 基线私有内存 MiB | 重构私有内存 MiB | 变化 |", "|---|---:|---:|---:|---:|---:|---:|"]
    metrics = {}
    scenarios = [("empty", "空配置 / 可见"), ("normal", "100 音频 / 可见"),
                 ("large", "1000 音频与壁纸记录 / 可见"), ("tray", "100 音频 / 托盘")]
    def compare(a, b):
        return (b / a - 1) * 100 if a else 0
    for key, title in scenarios:
        old = read(baseline / f"verified-baseline-{key}/summary.json")
        new = read(optimized / f"verified-{key}/summary.json")
        assert old["benchmark_sha256"] == new["benchmark_sha256"], "Benchmark versions differ"
        a, b = old["reports"], new["reports"]
        assert len(a) == len(b) == 5
        assert all(not report["errors"] for report in [*a, *b])
        times = [median(x["startup_ms"] for x in group) for group in (a, b)]
        memory = [median(x["initial"]["private"] for x in group) / MIB for group in (a, b)]
        metrics[key] = dict(startup_ms=times, private_mib=memory,
                            startup_ranges=[[min(x["startup_ms"] for x in group), max(x["startup_ms"] for x in group)] for group in (a,b)],
                            first_round_ms=[a[0]["startup_ms"], b[0]["startup_ms"]],
                            subsequent_median_ms=[median(x["startup_ms"] for x in a[1:]), median(x["startup_ms"] for x in b[1:])])
        lines.append(f"| {title} | {times[0]:.0f} | {times[1]:.0f} | {compare(*times):+.1f}% | {memory[0]:.1f} | {memory[1]:.1f} | {compare(*memory):+.1f}% |")
    lines += ["", "首轮不是独立冷盘实验；以下保留首轮与后续轮次，避免只选择较快的一次。", "",
              "| 场景 | 基线首轮 / 后四轮中位数 ms | 重构首轮 / 后四轮中位数 ms | 基线五轮范围 ms | 重构五轮范围 ms |",
              "|---|---:|---:|---:|---:|"]
    for key, title in scenarios:
        item = metrics[key]
        first, later, ranges = item["first_round_ms"], item["subsequent_median_ms"], item["startup_ranges"]
        lines.append(f"| {title} | {first[0]:.0f} / {later[0]:.0f} | {first[1]:.0f} / {later[1]:.0f} | {ranges[0][0]:.0f}–{ranges[0][1]:.0f} | {ranges[1][0]:.0f}–{ranges[1][1]:.0f} |")
    lines += ["", "## 大资源操作", "", "每轮重复五次资源操作，先求各轮中位数再比较五轮中位数；播放器与排队测试每轮一次。", "",
              "| 操作 | 基线 ms | 重构 ms | 变化 |", "|---|---:|---:|---:|"]
    old = read(baseline / "verified-baseline-large/summary.json")["reports"]
    new = read(optimized / "verified-large/summary.json")["reports"]
    for key, title in [("audio_scan", "直接文件发现"), ("playback_file_lookup", "播放候选索引读取"),
                       ("audio_table", "音频列表填充"), ("wallpaper_table", "壁纸列表填充"),
                       ("audio_search", "音频搜索"), ("wallpaper_search", "壁纸搜索"),
                       ("profile_switch", "当前配置重新载入"), ("playback_start", "静音音频进入播放状态"),
                       ("query_queue", "长任务占用时短查询等待")]:
        values = [median(median(report["operations"][key]) for report in group) for group in (old, new)]
        metrics[key] = values
        lines.append(f"| {title} | {values[0]:.2f} | {values[1]:.2f} | {compare(*values):+.1f}% |")
    first_access = median(r["operations"]["first_library_access"][0] for r in new)
    gui = [median(r["operation_gui_p95_ms"] for r in group) for group in (old, new)]
    cpu = [median(r["final"]["cpu"] - r["initial"]["cpu"] for r in group) for group in (old, new)]
    after_memory = [median(r["after_operations"]["private"] for r in group) / MIB for group in (old, new)]
    metrics["large_runtime"] = dict(operation_gui_p95_ms=gui, cpu_seconds=cpu, after_operations_private_mib=after_memory)
    lines += ["", f"首次创建两个资源库页面耗时中位数为 **{first_access:.0f} ms**。这是按需加载的实际成本；基线已在启动时创建这些页面。上表的列表填充仅统计数据提交，操作事件延迟与后台心跳另存于原始报告。",
              "", f"大资源操作期间 GUI 队列延迟 P95 的五轮中位数为 **{gui[0]:.1f} → {gui[1]:.1f} ms**；同组启动后的 CPU 时间为 **{cpu[0]:.2f} → {cpu[1]:.2f} s**；列表使用后的私有内存为 **{after_memory[0]:.1f} → {after_memory[1]:.1f} MiB**。",
              "", "小于数毫秒的差异易受调度和计时波动影响，不据此宣称可感知改善。所有新进程的起止、峰值工作集、CPU 时间、首轮/后续耗时和事件延迟保留在原始 JSON 中。", "",
              "## 长时间运行", "", "常驻十分钟、连续刷新三十分钟。以下比较前段稳定区间（第 60–120 秒）与末一分钟的私有内存中位数；测量器本身保留样本也会消耗少量内存。长测与短测期间本机存在其他验证任务，因此 CPU 和 GUI 尾延迟是观察值，不能视为专用空闲测试机结果。", "",
              "| 场景 | 源码 | 采样时长 s | 稳定前段 MiB | 最后一分钟 MiB | 差值 MiB |", "|---|---|---:|---:|---:|---:|"]
    for key, title in [("resident", "托盘常驻"), ("stress", "连续刷新")]:
        for label, folder in [("基线", baseline / f"verified-baseline-{key}"), ("重构", optimized / f"verified-{key}")]:
            report = read(folder / "summary.json")["reports"][0]
            samples = report["samples"]
            duration = samples[-1]["seconds"]
            assert duration >= (590 if key == "resident" else 1790)
            assert not report["errors"]
            early = median(s["private"] for s in samples if 60 <= s["seconds"] <= 120) / MIB
            late = median(s["private"] for s in samples if s["seconds"] >= duration - 60) / MIB
            minute_mib = [median(s["private"] for s in samples if minute*60 <= s["seconds"] < (minute+1)*60) / MIB
                          for minute in range(int(duration//60)+1)
                          if any(minute*60 <= s["seconds"] < (minute+1)*60 for s in samples)]
            metrics[f"{key}-{label}"] = dict(duration=duration, early_mib=early, late_mib=late, delta_mib=late-early, minute_mib=minute_mib,
                                             cpu_seconds=report["final"]["cpu"]-report["initial"]["cpu"], heartbeat_p95_ms=report["heartbeat_p95_ms"])
            lines.append(f"| {title} | {label} | {duration:.0f} | {early:.1f} | {late:.1f} | {late-early:+.1f} |")
    lines += ["", "初次长测的重构进程增加约 6 MiB，不能据此宣称内存稳定。该轮测量在进程内持续保存心跳和采样，且开始于 Future 引用释放修复之前，因此另用落盘采样复核最终整合代码。", ""]
    if integrated:
        data_runs = [read(baseline / "baseline-reused-data/summary.json"),
                     read(integrated / "output/performance/integrated-reused-data/summary.json")]
        assert data_runs[0]["benchmark_sha256"] == data_runs[1]["benchmark_sha256"]
        lines += ["## 首次创建数据与后续复用", "",
                  "100 音频、独立模式、可见窗口；每侧独立复用一个测试目录。首轮 Store 创建新数据，后四轮加载已存在配置。每轮重建相同合成音频的耗时被扣除；不复用真实个人数据。", "",
                  "| 数据状态 | 基线启动 ms | 最终整合版启动 ms |", "|---|---:|---:|"]
        fresh, reused = [], []
        for run in data_runs:
            assert len(run["reports"]) == 5 and run["arguments"]["reuse_data"]
            assert all(not report["errors"] for report in run["reports"])
            fresh.append(run["reports"][0]["startup_ms"])
            reused.append(median(report["startup_ms"] for report in run["reports"][1:]))
        metrics["fresh_vs_existing_data"] = dict(fresh_ms=fresh, existing_ms=reused)
        lines += [f"| 首次创建数据 | {fresh[0]:.0f} | {fresh[1]:.0f} |",
                  f"| 后四轮复用数据中位数 | {reused[0]:.0f} | {reused[1]:.0f} |", "",
                  "这组既有数据启动差异接近测量波动，不把全部启动场景都表述为稳定提速。托盘启动和资源操作改善更明确。原始目录为 `baseline-reused-data` / `integrated-reused-data`。", ""]
        access_runs = [read(baseline / "baseline-tray-access/summary.json"),
                       read(integrated / "output/performance/integrated-tray-access/summary.json")]
        assert access_runs[0]["benchmark_sha256"] == access_runs[1]["benchmark_sha256"]
        access_metrics = []
        assert read(optimized / "environment.json")["packages"] == read(integrated / "output/performance/environment.json")["packages"]
        for run in access_runs:
            reports = run["reports"]
            assert len(reports) == 5 and all(not r["errors"] for r in reports)
            access_metrics.append(dict(startup_ms=median(r["startup_ms"] for r in reports),
                                       first_window_ms=median(r["operations"]["first_window_access"][0] for r in reports),
                                       first_window_range_ms=[min(r["operations"]["first_window_access"][0] for r in reports), max(r["operations"]["first_window_access"][0] for r in reports)],
                                       reopen_window_ms=median(median(r["operations"]["reopen_window"]) for r in reports),
                                       combined_ms=median(r["startup_ms"]+r["operations"]["first_window_access"][0] for r in reports),
                                       initial_private_mib=median(r["initial"]["private"] for r in reports)/MIB,
                                       after_window_private_mib=median(r["after_first_window"]["private"] for r in reports)/MIB))
        metrics["tray_first_window"] = access_metrics
        lines += ["## 托盘首次开窗：明确保留的取舍", "",
                  "用户在看到五轮探针对比后，明确选择低常驻内存方案：不预热字体，接受首次开窗等待。最终通过真实托盘恢复入口 `show_window()` 测量，包含构建、显示和一次 GUI 事件处理。下面把启动与首次操作分开列出，合计按每轮相加后取中位数。", "",
                  "| 指标 | 基线 | 最终整合版 |", "|---|---:|---:|"]
        for key, title, precision in [("startup_ms", "托盘启动 ms", 0), ("first_window_ms", "首次开窗 ms", 0),
                                      ("combined_ms", "启动加首次开窗 ms", 0), ("reopen_window_ms", "后续开窗 ms", 1), ("initial_private_mib", "开窗前私有内存 MiB", 1),
                                      ("after_window_private_mib", "开窗后私有内存 MiB", 1)]:
            values = [entry[key] for entry in access_metrics]
            lines.append(f"| {title} | {values[0]:.{precision}f} | {values[1]:.{precision}f} |")
        access_range = access_metrics[1]["first_window_range_ms"]
        lines += ["", f"整合版首次开窗五轮范围为 **{access_range[0]/1000:.2f}–{access_range[1]/1000:.2f} 秒**。首次开窗是已接受的明显退化，不能宣称所有单项指标都改善。字体预热探针可把首次开窗降至约 1.16 秒，但托盘私有内存会升至约 100.7 MiB，因此未采用。显示前构建控件避免在已显示窗口中逐项布局；后续开窗不会再次构建编辑器。计时覆盖显示调用和一次 Qt 事件处理，不测量屏幕合成器最终呈现时刻。", ""]
        folders = [baseline / "baseline-stream-stress", integrated / "output/performance/integrated-stream-stress"]
        runs = [read(folder / "summary.json") for folder in folders]
        assert runs[0]["benchmark_sha256"] == runs[1]["benchmark_sha256"]
        lines += ["## 历史落盘采样复核（仍含 Mock 调用历史）", "",
                  "同一脚本把采样与计时写入 JSONL，最后一次内存快照之后才读回。每两秒刷新资源，并实际交替启用两个配置；保留播放器、日志和索引复核。此轮负载比前面的仅刷新长测更完整，分别与同脚本基线比较。", "",
                  "| 指标 | 基线 | 最终整合版 |", "|---|---:|---:|"]
        final_metrics = []
        for run in runs:
            report = run["reports"][0]
            samples = report["samples"]
            assert samples[-1]["seconds"] >= 1790 and not report["errors"]
            assert run["arguments"]["stream_metrics"] and run["arguments"]["switch_profiles"]
            windows = [median(s["private"] for s in samples if begin <= s["seconds"] < end) / MIB
                       for begin, end in [(60,120),(1200,1500),(1500,1800)]]
            final_metrics.append(dict(source_revision=run["source_revision"], duration_seconds=samples[-1]["seconds"],
                                      transitions=len(report["operations"]["profile_transition"]),
                                      early_private_mib=windows[0], minute20_25_private_mib=windows[1], minute25_30_private_mib=windows[2],
                                      tail_change_mib=windows[2]-windows[1], cpu_seconds=report["final"]["cpu"]-report["initial"]["cpu"],
                                      heartbeat_p95_ms=report["heartbeat_p95_ms"],
                                      profile_transition_ms=median(report["operations"]["profile_transition"])))
        metrics["final_streamed_stress"] = final_metrics
        for key, title, precision in [("duration_seconds", "采样时长 s", 0), ("transitions", "配置切换次数", 0),
                                      ("early_private_mib", "第 60–120 秒私有内存 MiB", 1),
                                      ("minute20_25_private_mib", "第 20–25 分钟私有内存 MiB", 1),
                                      ("minute25_30_private_mib", "第 25–30 分钟私有内存 MiB", 1),
                                      ("tail_change_mib", "后两个五分钟窗口差值 MiB", 2),
                                      ("cpu_seconds", "启动后累计 CPU 时间 s", 1),
                                      ("heartbeat_p95_ms", "GUI 心跳延迟 P95 ms", 1),
                                      ("profile_transition_ms", "配置切换耗时中位数 ms", 2)]:
            values = [entry[key] for entry in final_metrics]
            lines.append(f"| {title} | {values[0]:.{precision}f} | {values[1]:.{precision}f} |")
        lines += ["", f"长测记录提交为 `{runs[1]['source_revision']}`，应用代码与合并提交 `9c3977e` 相同。后续 `ce40a50` 仅在托盘恢复入口增加显示前构建；该入口不参与可见窗口长测，另通过五轮首次开窗和原生流程验证。逐秒数据位于整合工作区 `output/performance/integrated-stream-stress`，同脚本基线位于性能工作区 `output/baseline-source/output/performance/baseline-stream-stress`。", ""]
    lines += ["", "## 功能验证与审查", "",
              "性能分支完成 161 项单元测试、29 个原生流程。使用独立 Store、临时资源与模拟 API；未修改个人配置、音频、Wallpaper Engine 文件或现有模型服务。后续针对普通保存的过期输入、托盘模式和表格悬停样式另行执行了相应回归。", "",
              "Standards：已报告的 GUI 冷扫描、旧语言扫描旁路及错误文案本地化问题已修复；托盘模式恢复问题已修复。", "",
              "Spec：已报告的基准归属、启动/事件延迟口径、接口查询队列、目录监听边界、跨分钟触发及配置切换/保存后的过期输入问题已修复并复核关闭。", "",
              "## 复现与证据", "",
              "在性能 worktree 中使用 `.conda/python.exe scripts/benchmark_runtime.py --label my-run --items 1000 --mode wallpaper_engine`。常驻使用 `--tray --resident --seconds 600 --rounds 1`；连续刷新使用 `--stress --seconds 1800 --rounds 1`。", "",
              "基线从固定提交导出到 `output/baseline-source`，使用同一 Python 和同一基准脚本运行；`SOURCE_REVISION` 固定基线身份。每组 `summary.json` 记录基准脚本 SHA256、应用源码逐文件 SHA256、参数与全部原始轮次。", "",
              "五轮重构短测对应 `8b0313c`；十分钟与三十分钟重构长测在 `06338e3` 开始。之后的过期输入防护、表格样式及 Future 引用释放通过针对性回归验证，不能把较早长测称为最终提交的完整三十分钟验证。最终自动更新整合提交另做五轮短测与十分钟常驻，见整合记录。", "",
              "重构原始数据：`output/performance/verified-*`；基线原始数据：`output/baseline-source/output/performance/verified-baseline-*`；功能日志和审计：`output/ui-validation`。", "",
              "独立环境的 Python、平台与全部依赖版本记录于各工作区 `output/performance/environment.json`；整合版与性能版 30 项包版本逐项一致。历史五轮脚本保存为性能工作区 `output/performance/benchmark-verified.py`，落盘长测脚本保存为整合工作区 `output/performance/benchmark-streamed.py`，其 SHA256 与对应原始报告一致。", "",
              "交付为本地源码与提交；没有发布性能版、制作发行包或替换个人程序。自动更新的独立整合分支及其验证另见整合记录。", ""]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    (optimized / "comparison.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--integrated-root", type=Path)
    args = parser.parse_args()
    summarize(args.root, args.output or args.root / "docs/performance-report.md", args.integrated_root)
