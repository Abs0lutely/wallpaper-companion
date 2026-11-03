"""Isolated, repeatable native Qt benchmark; never connects to personal services."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]


def worker(args):
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    import psutil
    process = psutil.Process()
    with tempfile.TemporaryDirectory(prefix="bench-", dir=ROOT / "output") as directory, ExitStack() as stack:
        root = Path(directory)
        os.environ.update(WALLPAPER_COMPANION_DATA=str(root / "data"), GPT_SOVITS_DIR="")
        from companion import paths
        stack.enter_context(patch.object(paths, "discover_wallpaper_engine", return_value=("", "")))
        from companion import core, services
        stack.enter_context(patch.object(core, "discover_wallpaper_engine", return_value=("", "")))
        stack.enter_context(patch.object(services, "running_wallpaper_processes", return_value=[]))
        stack.enter_context(patch("companion.managed_api.api"))
        stack.enter_context(patch("requests.Session.request", side_effect=AssertionError("Network forbidden in benchmark")))
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from companion.ui import Window, STYLE
        stack.enter_context(patch("companion.ui.foreground_state", return_value=dict(desktop=True, fullscreen=False, own=False)))
        store = core.Store()
        store.config.update(run_mode=args.mode, we_dir="", workshop_dir="", library_roots=[])
        audio = root / "audio"
        audio.mkdir()
        for i in range(args.items):
            folder = audio / str(i // 100)
            folder.mkdir(exist_ok=True)
            with wave.open(str(folder / f"clip-{i:05}.wav"), "wb") as stream:
                stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                stream.writeframes(b"\0\0" * 800)
        if args.items:
            profile = core.new_profile("Benchmark")
            profile.update(voice_dir=str(audio), bgm_dir="", use_bundled_demo=False)
            store.config["profiles"] = [profile]
            store.config["standalone_profile"] = profile["id"]
        store.save()
        setup_end = time.perf_counter()
        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        w = Window(store, hooks=False)
        errors = []
        w.report_error = errors.append
        if not args.tray:
            w.show()
        app.processEvents()
        ready = time.perf_counter()
        def memory():
            info = process.memory_info()
            return dict(private=info.private, rss=info.rss, peak_rss=info.peak_wset,
                        cpu=sum(process.cpu_times()[:2]), threads=process.num_threads())
        result = dict(items=args.items, mode=args.mode, tray=args.tray,
                      startup_ms=(ready-setup_end)*1000, imports_ms=(setup_end-started)*1000,
                      initial=memory(), deferred_pages=list(getattr(w, "_page_builders", {})), operations={}, samples=[])
        def timed(name, fn):
            begin = time.perf_counter()
            fn()
            result["operations"].setdefault(name, []).append((time.perf_counter()-begin)*1000)
        if not args.resident:
            timed("first_library_access", lambda: (w.audio_table, w.library_table))
        # Native table population uses the same public callbacks as real scans.
        records = [dict(name=f"clip-{i:05}.wav", path=str(audio / str(i//100) / f"clip-{i:05}.wav"),
                        locations=["voice"], profiles=["benchmark"], bytes=1600, usages=[]) for i in range(args.items)]
        wallpapers = [dict(path=str(root / "wallpapers" / str(i)), title=f"Wallpaper {i}", type="scene", workshop_id=str(i)) for i in range(args.items)]
        def exercise():
            timed("audio_scan", lambda: core.audio_files(str(audio)))
            timed("audio_table", lambda: w.audio_library_scanned(dict(records=records, warnings=[])))
            w.library_records = wallpapers
            timed("wallpaper_table", w.render_library)
            assert w.audio_table.rowCount() == args.items
            assert w.library_table.rowCount() == args.items
            timed("audio_search", lambda: w.audio_search.setText("999" if not w.audio_search.text() else ""))
            timed("wallpaper_search", lambda: w.library_search.setText("999" if not w.library_search.text() else ""))
        if not args.resident:
            for _ in range(5):
                exercise()
                app.processEvents()
            result["after_operations"] = memory()
        last = time.perf_counter()
        lags = []
        heartbeat = QTimer()
        heartbeat.setInterval(50)
        def beat():
            nonlocal last
            now = time.perf_counter()
            lags.append(max(0, (now-last)*1000-50))
            last = now
        heartbeat.timeout.connect(beat)
        heartbeat.start()
        sampler = QTimer()
        sampler.setInterval(1000)
        sampler.timeout.connect(lambda: result["samples"].append(dict(seconds=time.perf_counter()-ready, **memory())))
        sampler.start()
        repeater = QTimer()
        repeater.setInterval(2000)
        if args.stress:
            repeater.timeout.connect(exercise)
            repeater.start()
        QTimer.singleShot(int(args.seconds*1000), app.quit)
        app.exec()
        result.update(final=memory(), errors=errors, heartbeat_p95_ms=sorted(lags)[int(.95*(len(lags)-1))] if lags else 0)
        w.cleanup()
        w.close()
        app.processEvents()
        Path(args.report).write_text(json.dumps(result, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--report")
    parser.add_argument("--items", type=int, default=1000)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--mode", choices=["standalone", "wallpaper_engine"], default="standalone")
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--resident", action="store_true")
    parser.add_argument("--stress", action="store_true")
    args = parser.parse_args()
    (ROOT / "output").mkdir(exist_ok=True)
    if args.worker:
        worker(args)
        return
    output = ROOT / "output" / "performance" / args.label
    output.mkdir(parents=True, exist_ok=True)
    metadata = dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    python=sys.version, executable=sys.executable, arguments=vars(args), reports=[])
    for i in range(args.rounds):
        report = output / f"round-{i+1}.json"
        command = [sys.executable, str(Path(__file__)), "--worker", "--report", str(report),
                   "--items", str(args.items), "--seconds", str(args.seconds), "--mode", args.mode]
        command += [flag for flag, enabled in [("--tray", args.tray), ("--resident", args.resident), ("--stress", args.stress)] if enabled]
        with (output / f"round-{i+1}.log").open("w", encoding="utf-8") as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=args.seconds+120)
        data = json.loads(report.read_text(encoding="utf-8"))
        metadata["reports"].append(data)
        print(f"{args.label} {i+1}: startup={data['startup_ms']:.1f}ms private={data['initial']['private']/1048576:.1f}MiB", flush=True)
    (output / "summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
