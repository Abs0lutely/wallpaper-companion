"""Native timer/tray regression: no child GUI launches or hidden label writes."""
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QPushButton
from companion.core import ROOT, Store, new_profile
from companion.ui import STYLE, Window

output = ROOT / "output"; output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
root = Path(fixture.name).resolve()
we = root / "engine"; we.mkdir()
paths = []
for name in ("first", "second"):
    folder = root / name; folder.mkdir()
    file = folder / "scene.mp4"; file.touch(); paths.append(file)

def select(path):
    (we / "config.json").write_text(json.dumps({"fixture-user": {"general": {
        "wallpaperconfig": {"selectedwallpapers": {"Monitor0": {"file": str(path)}}}}}}), encoding="utf-8")

select(paths[0])
store = Store(root / "data/config.json")
store.config.update(we_dir=str(we), workshop_dir="", hover_help=False)
for index, name in enumerate(("first", "second")):
    p = new_profile(name, str(paths[index]))
    p.update(bgm_enabled=False, rules=[])
    store.config["profiles"].append(p)
store.save()
app = QApplication([]); app.setStyle("Fusion"); app.setStyleSheet(STYLE)
state = dict(desktop=False, fullscreen=False, own=False)
patches = [patch("companion.services.running_wallpaper_processes", return_value=[dict(exe=str(we / "wallpaper64.exe"), name="wallpaper64.exe")]),
           patch("companion.services.run_external", return_value=SimpleNamespace(returncode=0, stdout=str(paths[1]).encode())),
           patch("companion.ui.foreground_state", side_effect=lambda: state.copy()),
           patch("companion.managed_api.api")]
for item in patches:
    item.start()
from companion import services
launch = services.run_external
w = Window(store, hooks=False)
w.registry.audio_detectors["builtin"] = ("fixture", lambda *_: dict(state="no", detail="fixture"))
w.poll.setInterval(120)
w.show()
calls, report, errors = [], {}, []
w.report_error = errors.append
original_detected = w.detected
def detected(result):
    calls.append(result)
    original_detected(result)
w.detected = detected
counter = dict(show=0, paint=0)

class Events(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            counter["show"] += 1
        if event.type() == QEvent.Type.Paint:
            counter["paint"] += 1
        return False

events = Events(w)
w.installEventFilter(events)
spies = [patch.object(widget, "setText", wraps=widget.setText) for widget in (w.current_label, w.status_label, w.bgm_pause_button)]
mocks = [spy.start() for spy in spies]
deadline = time.monotonic() + 20

def fail(exc):
    print("FAILED", repr(exc), errors)
    w.cleanup(); app.exit(2)

def guard(action):
    def run():
        try:
            action()
        except Exception as exc:
            fail(exc)
    return run

def wait(predicate, action):
    if predicate():
        QTimer.singleShot(30, guard(action))
    elif time.monotonic() >= deadline:
        fail(TimeoutError("polling regression timed out"))
    else:
        QTimer.singleShot(40, lambda: wait(predicate, action))

def initial():
    report["visible_auto_detection_works"] = w.active_id == store.config["profiles"][0]["id"]
    for mock in mocks:
        mock.reset_mock()
    count = len(calls)
    wait(lambda: len(calls) >= count + 8, visible_checked)

def visible_checked():
    report["unchanged_visible_status_not_rewritten"] = all(mock.call_count == 0 for mock in mocks)
    report["visible_poll_has_no_gui_subprocess"] = launch.call_count == 0
    w.hide()
    app.processEvents()
    for mock in mocks:
        mock.reset_mock()
    counter.update(show=0, paint=0)
    state["fullscreen"] = True
    w.on_tick()
    select(paths[1])
    count = len(calls)
    wait(lambda: len(calls) >= count + 10 and w.active_id == store.config["profiles"][1]["id"], hidden_checked)

def hidden_checked():
    report["hidden_fullscreen_keeps_following_wallpaper"] = w.current["path"] == str(paths[1])
    report["hidden_status_not_rewritten"] = all(mock.call_count == 0 for mock in mocks)
    report["hidden_window_never_shown_or_painted"] = counter["show"] == 0 and counter["paint"] == 0 and not w.isVisible()
    report["hidden_poll_has_no_gui_subprocess"] = launch.call_count == 0
    w.show_window()
    state["fullscreen"] = False
    w.on_tick()
    report["restore_synchronizes_latest_state"] = "second" in w.current_label.text() and "second" in w.status_label.text()
    w.poll.stop()
    wait(lambda: not w.query_busy, explicit_check)

def explicit_check():
    next(b for b in w.findChildren(QPushButton) if b.text() == "立即检测").click()
    wait(lambda: not w.query_busy, finish)

def finish():
    report["manual_check_can_query_once"] = launch.call_count == 1 and "getWallpaper" in launch.call_args.args[0]
    report["query_flag_not_persisted"] = "_wallpaper_command_query" not in store.config and "_wallpaper_command_query" not in store.path.read_text(encoding="utf-8")
    report["no_errors"] = not errors
    w.grab().save(str(output / "polling-flicker.png"))
    (output / "smoke-polling-flicker.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    w.cleanup(); app.exit(0 if all(report.values()) else 1)

QTimer.singleShot(300, lambda: wait(lambda: w.active_id is not None, initial))
QTimer.singleShot(22000, lambda: app.exit(3))
code = app.exec()
w.cleanup()
for spy in spies:
    spy.stop()
for item in reversed(patches):
    item.stop()
import shiboken6
shiboken6.delete(w)
fixture.cleanup()
sys.exit(code)
