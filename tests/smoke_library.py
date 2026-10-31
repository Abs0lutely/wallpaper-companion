"""Native UI workflow for discovery, batch binding and editable starter dialogues."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from companion.core import ROOT, Store
from companion.ui import Window, STYLE

output = ROOT / "output"
output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
temp = Path(fixture.name)
wallpapers = temp / "wallpapers"
for index, title in enumerate(["晨间山景", "夜间星空"], 1):
    folder = wallpapers / str(index)
    folder.mkdir(parents=True)
    (folder / "scene.pkg").write_bytes(b"fixture")
    (folder / "project.json").write_text(json.dumps(dict(title=title, file="scene.pkg", type="scene")), encoding="utf-8")
voice = temp / "shared-voice"
voice.mkdir()
store = Store(temp / "app/config.json")
store.config.update(we_dir=str(temp / "missing-engine"), workshop_dir=str(wallpapers))
app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
w = Window(store, hooks=False)
w.show()
report = {}

def run_checks():
    try:
        report["discovered_in_background"] = len(w.library_records) == 2
        assert report["discovered_in_background"]
        w.tabs.setCurrentIndex(w.library_tab_index)
        w.check_library(True)
        report["bulk_selection"] = len(w.checked_wallpapers()) == 2
        result = w.apply_library_bindings(w.checked_wallpapers(), dict(mode="shared", voice_dir=str(voice)))
        report["batch_created_two"] = result["created"] == 2 and len(store.config["profiles"]) == 2
        app.processEvents()
        assert w.grab().save(str(output / "wallpaper-library.png"))
        report["starter_dialogues_loaded"] = len(w.edit_dialogues) == 38
        w.edit_dialogues[0]["text"] = "用户自己修改的台词。"
        w.render_dialogues()
        w.dialogue_table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
        report["save_dialogues"] = w.save_profile()
        loaded = Store(store.path).profile(w.editing_id)
        report["dialogue_edits_persist"] = loaded["dialogues"][0]["text"] == "用户自己修改的台词。" and not loaded["dialogues"][1]["enabled"]
        w.tabs.setCurrentIndex(w.dialogue_tab_index)
        app.processEvents()
        assert w.grab().save(str(output / "dialogue-library.png"))
        w.send_dialogues_to_tts()
        report["dialogues_sent_to_generation"] = len(w.lines.toPlainText().splitlines()) == 37 and "用户自己修改" in w.lines.toPlainText()
        w.library_search.setText("星空")
        w.check_library(False)
        report["filter_preserves_hidden_checks"] = len(w.checked_wallpapers()) == 1
        (output / "smoke-library.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report))
        w.cleanup()
        app.exit(0 if all(report.values()) else 1)
    except Exception:
        import traceback
        traceback.print_exc()
        w.cleanup()
        app.exit(2)

QTimer.singleShot(1800, run_checks)
QTimer.singleShot(15000, lambda: (w.cleanup(), app.exit(3)))
code = app.exec()
import shiboken6
shiboken6.delete(w)
fixture.cleanup()
sys.exit(code)
