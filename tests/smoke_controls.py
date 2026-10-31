"""Native end-to-end controls without modifying real wallpaper/startup settings."""
import json
import struct
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QMessageBox
from companion.core import ROOT, Store, new_profile
from companion.ui import Window, STYLE

output = ROOT / "output"
fixture = tempfile.TemporaryDirectory(dir=output)
temp = Path(fixture.name)
for name in ["voice", "bgm"]:
    (temp / name).mkdir()
    with wave.open(str(temp / name / "test.wav"), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000 * 10)
store = Store(temp / "app/config.json")
p = new_profile("控制验证", str(temp / "voice/test.wav"))
p.update(voice_dir=str(temp / "voice"), bgm_dir=str(temp / "bgm"), desktop_only=False)
store.config["profiles"] = [p]
store.config["manual_profile"] = p["id"]
store.save()
app = QApplication([])
app.setStyle("Fusion"); app.setStyleSheet(STYLE)
w = Window(store, hooks=False)
w.show()
report = {}

def guard(fn):
    def run():
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc(); w.cleanup(); app.exit(2)
    return run

@guard
def first():
    report["original_audio_detected"] = w.original_audio["state"] == "yes"
    report["conflict_blocks_bgm"] = w.audio.bgm_blocked and w.audio.bgm.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    w.original_audio_override.setCurrentIndex(w.original_audio_override.findData("no"))
    assert w.save_profile()
    QTimer.singleShot(600, volume)

@guard
def volume():
    report["override_allows_bgm"] = w.audio.bgm.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    track = w.audio.bgm.source()
    w.bgm_volume.setValue(37)
    report["volume_live_and_persisted"] = abs(w.audio.bgm_output.volume() - .37) < .01 and Store(store.path).profile(p["id"])["bgm_volume"] == 37
    report["volume_keeps_track"] = w.audio.bgm.source() == track
    w.preview_voice()
    QTimer.singleShot(400, pause)

@guard
def pause():
    w.toggle_bgm()
    report["bgm_pause_keeps_voice"] = w.audio.busy and w.audio.bgm.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    w.toggle_pause(); w.toggle_pause()
    report["global_resume_keeps_bgm_paused"] = w.audio.bgm_paused and w.audio.bgm.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    assert w.save_profile()
    report["profile_save_keeps_bgm_paused"] = w.audio.bgm_paused
    w.toggle_bgm()
    QTimer.singleShot(500, resources)

@guard
def resources():
    report["bgm_resume"] = w.audio.bgm.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    # Bind two disposable entries to one resource root using the same function as the dialog.
    records = []
    for index in range(2):
        file = temp / f"wallpaper-{index}.pkg"; file.write_bytes(b"fixture")
        records.append(dict(path=str(file), title=f"共享-{index}", type="scene", workshop_id="", project="", source="", directory=str(temp)))
    result = w.apply_library_bindings(records, dict(mode="shared_root", asset_dir=str(temp / "shared")))
    report["shared_root_batch_bound"] = result["created"] == 2
    shared = store.config["profiles"][-2:]
    w.refresh_profiles(shared[0]["id"])
    w.edit_dialogues[0]["text"] = "共享文本更新。"; w.render_dialogues(); assert w.save_profile()
    w.refresh_profiles(shared[1]["id"])
    report["shared_dialogues_ui_sync"] = w.edit_dialogues[0]["text"] == "共享文本更新。"
    startup = {"enabled": False}
    def set_value(enabled): startup["enabled"] = enabled
    with patch("companion.startup.startup_enabled", side_effect=lambda: startup["enabled"]), patch("companion.startup.set_startup", side_effect=set_value):
        w.startup_button.click(); report["startup_button_enables"] = startup["enabled"] and "已开启" in w.startup_button.text()
        w.startup_button.click(); report["startup_button_disables"] = not startup["enabled"] and "已关闭" in w.startup_button.text()
    app.processEvents(); assert w.grab().save(str(output / "controls.png"))
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        w.delete_profile_ids([q["id"] for q in shared])
    report["bulk_delete_keeps_resources"] = len(store.config["profiles"]) == 1 and (temp / "shared/dialogues.json").is_file() and all(Path(r["path"]).is_file() for r in records)
    (output / "smoke-controls.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    w.cleanup(); app.exit(0 if all(report.values()) else 1)

QTimer.singleShot(1800, first)
QTimer.singleShot(18000, lambda: (w.cleanup(), app.exit(3)))
code = app.exec()
import shiboken6
shiboken6.delete(w)
fixture.cleanup()
sys.exit(code)
