"""Native audio library workflow, only disposable files and a fake API lifecycle."""
import json
import sys
import tempfile
import time
import traceback
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from companion.assets import attach_resources, shared_root, private_root
from companion.core import Store, new_profile, ROOT
from companion.resources_ui import ResourceDialog
from companion.ui import Window, STYLE

output = ROOT / "output"
output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
root = Path(fixture.name)
store = Store(root / "data/config.json")
store.config.update(we_dir=str(root / "no-we"), workshop_dir=str(root / "no-workshop"))
one = attach_resources(new_profile("音频库测试壁纸"), shared_root(store))
two = attach_resources(new_profile("共用语音的另一壁纸"), shared_root(store))
store.config["profiles"] = [one, two]
store.save()

def wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
        f.writeframes(b"\x00\x00" * 16000 * 4)

shared = Path(one["voice_dir"]) / "你好.wav"
wav(shared)
imported = root / "download/早上好.wav"
private_location = root / "custom-private"
wav(imported)
app = QApplication([])
app.setStyle("Fusion"); app.setStyleSheet(STYLE)
api_patch = patch("companion.managed_api.api")
api_guard = api_patch.start()
w = Window(store, hooks=False)
w.show()
report = {}
errors = []
w.report_error = lambda text: errors.append(text)
deadline = time.monotonic() + 35

def wait(predicate, action):
    if predicate():
        QTimer.singleShot(100, guard(action))
    elif time.monotonic() > deadline:
        fail(RuntimeError("Native workflow timed out"))
    else:
        QTimer.singleShot(80, lambda: wait(predicate, action))

def fail(exc):
    traceback.print_exc()
    print(exc, errors)
    w.cleanup(); app.exit(2)

def guard(fn):
    def call():
        try:
            fn()
        except Exception as exc:
            fail(exc)
    return call

def initial():
    w.refresh_profiles(one["id"])
    # Exercise the real mode dialog and saved per-channel results.
    dialog = ResourceDialog(store, w.draft_profile(), w, dedicated=True)
    dialog.root.setText(str(private_location))
    dialog.modes["voice_dir"].setCurrentIndex(dialog.modes["voice_dir"].findData("shared"))
    assert w.apply_resource_profile(dialog.apply())
    actual = Store(store.path).profile(one["id"])
    report["mixed_modes_saved"] = actual["voice_dir"] == str(shared.parent) and actual["bgm_dir"] == str(private_location / "bgm")
    reopened = ResourceDialog(store, actual, w)
    report["custom_private_root_remembered"] = reopened.root.text() == str(private_location)
    report["source_preserved"] = shared.is_file()
    w.tabs.setCurrentIndex(w.audio_library_tab_index)
    wait(lambda: not w.audio_library_busy and len(w.audio_records) == 1, inventory_ready)

def inventory_ready():
    report["shared_file_deduplicated"] = len(w.audio_records) == 1 and len(w.audio_records[0]["profiles"]) == 2
    w.audio_table.clearSelection()
    with patch.object(w, "open_folder") as opened:
        w.open_library_audio_folder()
        report["no_selection_opens_first_directory"] = opened.call_args.args[0] == str(shared.parent)
    w.audio_table.selectRow(0)
    w.preview_library_audio()
    wait(lambda: w.audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState, preview_ready)

def preview_ready():
    report["real_preview_plays"] = True
    w.audio.voice.stop()
    w.audio_target.setCurrentIndex(w.audio_target.findData(one["id"] + ":bgm"))
    w.audio_category.setText("导入分类")
    with patch.object(QFileDialog, "getOpenFileNames", return_value=([str(imported)], "")):
        w.import_library_audio()
    wait(lambda: not w.audio_library_busy and len(w.audio_records) == 2, copied)

def copied():
    target = private_location / "bgm/导入分类/早上好.wav"
    report["import_to_private_category"] = target.is_file() and imported.is_file()
    w.audio_search.setText("早上好")
    report["search_filters"] = sum(not w.audio_table.isRowHidden(i) for i in range(w.audio_table.rowCount())) == 1
    w.select_library_audio(True)
    report["select_all_respects_filter"] = len(w.selected_library_audio()) == 1
    w.audio_search.clear()
    w.select_library_audio(True)
    report["multiple_audio_selection"] = len(w.selected_library_audio()) == 2
    w.select_library_audio(False)
    report["clear_audio_selection"] = not w.selected_library_audio()
    w.audio_category.clear()
    w.audio_target.setCurrentIndex(w.audio_target.findData("shared:voice"))
    w.reference_audio_target("voice_dir")
    wait(lambda: not w.audio_library_busy, referenced)

def referenced():
    report["folder_reference_no_copy"] = Store(store.path).profile(one["id"])["voice_dir"] == str(shared.parent)
    # Recycle a private test file for real; never recycle user content.
    row = next(i for i, item in enumerate(w.audio_records) if item["name"] == "早上好.wav")
    w.audio_table.selectRow(row)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        w.recycle_library_audio()
    wait(lambda: not w.audio_library_busy and len(w.audio_records) == 1, recycled)

def recycled():
    report["private_recycled_shared_preserved"] = shared.exists() and imported.exists() and not (private_location / "bgm/导入分类/早上好.wav").exists()
    old_voice = Store(store.path).profile(one["id"])["voice_dir"]
    w.shared_audio_root.setText(str(root / "custom-shared"))
    w.save_shared_audio_root()
    wait(lambda: not w.audio_library_busy, lambda: finish(old_voice))

def finish(old_voice):
    report["custom_shared_root_preserves_bindings"] = Store(store.path).profile(one["id"])["voice_dir"] == old_voice
    report["no_ui_errors"] = not errors
    report["browsing_never_starts_api"] = not api_guard.ensure.called
    w.resize(1280, 900)
    app.processEvents()
    w.grab().save(str(output / "audio-library.png"))
    w.cleanup()
    report["exit_shuts_down_owned_api_manager"] = api_guard.shutdown.called
    (output / "smoke-audio-library.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    app.exit(0 if all(report.values()) else 1)

QTimer.singleShot(700, guard(initial))
QTimer.singleShot(40000, lambda: app.exit(3))
result = app.exec()
w.cleanup()
api_patch.stop()
fixture.cleanup()
sys.exit(result)
