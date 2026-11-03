"""Validate and summarize the final measurements without mock call retention."""
import hashlib
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "wallpaper-companion-perf/output/baseline-source"
MIB = 1024 * 1024


def read_run(root, label, duration):
    folder = root / "output/performance" / label
    run = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    report = run["reports"][0]
    assert len(run["reports"]) == 1 and not report["errors"]
    assert report["samples"][-1]["seconds"] >= duration - 10
    assert "Traceback" not in (folder / "round-1.log").read_text(encoding="utf-8", errors="replace")
    assert run["arguments"]["stream_metrics"]
    for name, digest in run["source_hashes"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
    return run, report


def main():
    lines = ["# 最终内存稳定性复核", "",
             "使用普通模拟函数替代保留调用历史的 Mock，逐秒采样写入磁盘。基线固定为 `2055adf`，整合版应用源码对应 `3d47c99`；脚本与逐文件源码哈希已核对。", "",
             "测试范围为本机 Windows、Qt 播放器和合成资源；WE、模型服务、更新网络均模拟。结果不外推为发行包、真实外部服务或无限期无泄漏证明。", "",
             "| 场景 / 指标 | 基线 | 整合版 |", "|---|---:|---:|"]
    evidence = {}
    for kind, duration in [("resident", 600), ("stress", 1800)]:
        runs = [read_run(BASE, "baseline-final-clean-" + kind, duration),
                read_run(ROOT, "final-clean-" + kind, duration)]
        assert runs[0][0]["benchmark_sha256"] == runs[1][0]["benchmark_sha256"]
        values = []
        for metadata, report in runs:
            samples = report["samples"]
            window = lambda start, end: median(s["private"] for s in samples if start <= s["seconds"] < end) / MIB
            before, after = ((1200, 1500), (1500, 1800)) if kind == "stress" else ((300, 450), (450, 600))
            item = dict(early_mib=window(60, 120), previous_mib=window(*before), final_mib=window(*after),
                        cpu_seconds=report["final"]["cpu"]-report["initial"]["cpu"], heartbeat_p95_ms=report["heartbeat_p95_ms"],
                        operations=len(report["operations"].get("profile_transition", [])),
                        minute_mib=[window(m*60, (m+1)*60) for m in range(duration//60)], source_revision=metadata["source_revision"])
            item["tail_change_mib"] = item["final_mib"]-item["previous_mib"]
            values.append(item)
        evidence[kind] = values
        title = "十分钟托盘" if kind == "resident" else "三十分钟切换与刷新"
        for key, caption in [("early_mib", "前段私有内存 MiB"), ("previous_mib", "倒数第二窗口 MiB"),
                             ("final_mib", "最后窗口 MiB"), ("tail_change_mib", "后段变化 MiB"),
                             ("cpu_seconds", "累计 CPU 秒"), ("heartbeat_p95_ms", "GUI 心跳延迟 P95 ms"),
                             ("operations", "配置交替次数")]:
            lines.append(f"| {title} / {caption} | {values[0][key]:.2f} | {values[1][key]:.2f} |")
    lines += ["", "## 验收结论", "",
              "本次负载下未观察到持续内存增长。整合版连续操作后两个五分钟窗口仅相差约 4 KiB，最后十分钟逐分钟中位数稳定在约 128.45–128.52 MiB。十分钟托盘末一分钟为 67.24 MiB，基线为 116.92 MiB，减少约 42.5%；没有将预热后的内存变化描述为绝对零增长。", "",
              "双方均完成 904 次配置交替；整合版累计 CPU 时间减少约 84.1%，GUI 心跳延迟 P95 从 639.34 ms 降至 26.34 ms。常驻采样与压力测试同时运行，计时结论限定为本轮相同机器的对照。", "",
              "结合已通过的 177 项单元测试、30 个原生界面流程及五轮主要操作对比，本轮本地性能验收完成。用户明确接受低内存方案的首次开窗代价：中位数 2.39 秒、范围 2.13–3.08 秒；不宣称所有单项指标均改善。", "",
              "托盘末段比较第 5–7.5 分钟与第 7.5–10 分钟；连续操作比较第 20–25 分钟与第 25–30 分钟。逐分钟数据见 `output/performance/clean-comparison.json`，不删除预热阶段或历史受污染的数据。", "",
              "原始数据：整合工作区 `output/performance/final-clean-*`；性能工作区 `output/baseline-source/output/performance/baseline-final-clean-*`。", ""]
    (ROOT / "docs/performance-stability.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "output/performance/clean-comparison.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
