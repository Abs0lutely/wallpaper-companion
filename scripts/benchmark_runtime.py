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
    started = float(args.started) if args.started else time.perf_counter()
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
        fixture_started = time.perf_counter()
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
        fixture_seconds = setup_end - fixture_started
        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        import inspect
        options = {"defer_editor": args.tray} if "defer_editor" in inspect.signature(Window).parameters else {}
        w = Window(store, hooks=False, **options)
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
                      startup_ms=(ready-started-fixture_seconds)*1000, window_ms=(ready-setup_end)*1000, fixture_ms=fixture_seconds*1000,
                      initial=memory(), deferred_pages=list(getattr(w, "_page_builders", {})), operations={}, samples=[])
        operation_lags = []
        def timed(name, fn):
            queued = time.perf_counter()
            QTimer.singleShot(0, lambda: operation_lags.append((time.perf_counter()-queued)*1000))
            begin = time.perf_counter()
            fn()
            result["operations"].setdefault(name, []).append((time.perf_counter()-begin)*1000)
            app.processEvents()
        if not args.resident:
            if hasattr(w, "ensure_editor"):
                timed("first_editor_access", w.ensure_editor)
            timed("first_library_access", lambda: (w.audio_table, w.library_table))
        # Native table population uses the same public callbacks as real scans.
        records = [dict(name=f"clip-{i:05}.wav", path=str(audio / str(i//100) / f"clip-{i:05}.wav"),
                        locations=["voice"], profiles=["benchmark"], bytes=1600, usages=[]) for i in range(args.items)]
        wallpapers = [dict(path=str(root / "wallpapers" / str(i)), title=f"Wallpaper {i}", type="scene", workshop_id=str(i)) for i in range(args.items)]
        def exercise():
            timed("audio_scan", lambda: core.audio_files(str(audio)))
            lookup = w.audio_index.files if hasattr(w, "audio_index") else core.audio_files
            def resolve_lookup():
                deadline = time.perf_counter() + 5
                while True:
                    try:
                        return lookup(str(audio))
                    except Exception as exc:
                        if type(exc).__name__ != "IndexPending" or time.perf_counter() > deadline:
                            raise
                        w.audio_index.defer(exc, "benchmark", lambda: None)
                        app.processEvents()
                        time.sleep(.001)
            timed("playback_file_lookup", resolve_lookup)
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
        if not args.resident:
            timed("profile_switch", lambda: w.refresh_profiles())
            if args.items:
                from PySide6.QtMultimedia import QMediaPlayer
                track = audio / "0" / "clip-00000.wav"
                w.audio.voice_output.setVolume(0)
                begin = time.perf_counter()
                w.audio.play_voice(track)
                deadline = begin + 3
                while w.audio.voice.playbackState() != QMediaPlayer.PlaybackState.PlayingState and time.perf_counter() < deadline:
                    app.processEvents()
                    time.sleep(.002)
                result["playback_started"] = w.audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                result["operations"]["playback_start"] = [(time.perf_counter()-begin)*1000]
                w.audio.stop()
            import threading
            release = threading.Event()
            for _ in range(3):
                w.submit(lambda: release.wait(.15), lambda _: None)
            completed = []
            begin = time.perf_counter()
            options = {"lane": "query"} if "lane" in inspect.signature(w.submit).parameters else {}
            w.submit(lambda: time.perf_counter(), lambda stamp: completed.append(stamp), **options)
            deadline = begin + 3
            while not completed and time.perf_counter() < deadline:
                app.processEvents()
                time.sleep(.002)
            release.set()
            assert completed, "Query did not complete"
            result["operations"]["query_queue"] = [(completed[0]-begin)*1000]
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
        result.update(final=memory(), errors=errors, operation_gui_max_ms=max(operation_lags, default=0), operation_gui_p95_ms=sorted(operation_lags)[int(.95*(len(operation_lags)-1))] if operation_lags else 0, heartbeat_p95_ms=sorted(lags)[int(.95*(len(lags)-1))] if lags else 0)
        w.cleanup()
        w.close()
        app.processEvents()
        Path(args.report).write_text(json.dumps(result, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--started")
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
    import hashlib
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT / "main.py", *sorted((ROOT / "companion").glob("*.py"))]}
    metadata = dict(source_hashes=source_hashes, commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    python=sys.version, executable=sys.executable, arguments=vars(args), reports=[])
    for i in range(args.rounds):
        report = output / f"round-{i+1}.json"
        command = [sys.executable, str(Path(__file__)), "--worker", "--report", str(report),
                   "--items", str(args.items), "--seconds", str(args.seconds), "--mode", args.mode]
        command += [flag for flag, enabled in [("--tray", args.tray), ("--resident", args.resident), ("--stress", args.stress)] if enabled]
        with (output / f"round-{i+1}.log").open("w", encoding="utf-8") as log:
            command += ["--started", str(time.perf_counter())]
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=args.seconds+120)
        data = json.loads(report.read_text(encoding="utf-8"))
        metadata["reports"].append(data)
        print(f"{args.label} {i+1}: startup={data['startup_ms']:.1f}ms private={data['initial']['private']/1048576:.1f}MiB", flush=True)
    (output / "summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
