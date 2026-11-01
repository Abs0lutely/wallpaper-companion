"""Fresh-install shared dialogue operations without a wallpaper binding or API."""
import json
import io
import time
import wave
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton
from companion.assets import shared_root, load_dialogues
from companion.core import ROOT, Store
from companion.ui import Window, STYLE
import shiboken6

output = ROOT / "output"
output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
root = Path(fixture.name)
store = Store(root / "data/config.json")
store.config.update(we_dir="", workshop_dir="")
app = QApplication([])
app.setStyle("Fusion"); app.setStyleSheet(STYLE)
app.setQuitOnLastWindowClosed(False)
api_patch = patch("companion.managed_api.api")
api = api_patch.start()
w = Window(store, hooks=False)
w.show(); w.navigation[5].click()
report, errors = {}, []
w.report_error = errors.append

def click(text):
    next(b for b in w.findChildren(QPushButton) if b.text() == text).click()

def run():
    try:
        library = shared_root(store) / "dialogues.json"
        report["fresh_shows_38_without_creating_profile_or_file"] = w.dialogue_table.rowCount() == 38 and not store.config["profiles"] and not library.exists()
        w.edit_dialogues = []; w.render_dialogues()
        click("补充默认台词")
        report["supplement_button_works_without_binding"] = w.dialogue_table.rowCount() == 38 and "38" in w.dialogue_context.text()
        click("补充默认台词")
        report["supplement_idempotent_with_feedback"] = w.dialogue_table.rowCount() == 38 and "齐全" in w.dialogue_context.text()
        w.edit_dialogues[0]["text"] = "不必急着证明自己，你能回来，就值得一句欢迎。"
        w.render_dialogues()
        w.dialogue_table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
        click("保存台词库")
        saved = load_dialogues(dict(dialogue_file=str(library)))
        report["shared_save_preserves_data_independent_of_generation_selection"] = saved[0]["text"] == w.edit_dialogues[0]["text"] and saved[1]["enabled"] and not store.config["profiles"]
        other = Window(Store(store.path), hooks=False)
        report["reopen_restores_shared_library"] = other.edit_dialogues == saved
        other.cleanup(); shiboken6.delete(other)
        imported = root / "import.json"
        imported.write_bytes((ROOT / "examples/dialogues/heartfelt-zh-CN.json").read_bytes())
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(imported), "")):
            click("导入台词 JSON / TXT"); click("导入台词 JSON / TXT")
        report["import_actual_72_line_pack_without_binding_deduplicates"] = len(w.edit_dialogues) == 110 and len({e["category"] for e in w.edit_dialogues}) == 6
        exported = root / "export.json"
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(exported), "")):
            click("导出台词 JSON")
        report["export_without_binding"] = len(json.loads(exported.read_text(encoding="utf-8"))) == 110
        before = library.read_bytes()
        with patch("companion.assets.write_dialogues", side_effect=OSError("fixture write failed")):
            report["save_failure_keeps_original_file"] = not w.save_dialogue_library() and library.read_bytes() == before
        assert "fixture write failed" in errors.pop()
        audio = io.BytesIO()
        with wave.open(audio, "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b"\x01\x00" * 160)
        api.synthesize.return_value = audio.getvalue()
        for i in range(w.dialogue_table.rowCount()):
            w.dialogue_table.item(i, 0).setCheckState(Qt.CheckState.Checked if i == 0 else Qt.CheckState.Unchecked)
        w.generate_dialogue_library()
        deadline = time.monotonic() + 6
        while w.tts_busy and time.monotonic() < deadline:
            QTest.qWait(20)
        report["categorized_generation_without_binding_uses_shared_voice"] = not w.tts_busy and len(list((shared_root(store) / "voice").rglob("*.wav"))) == 1 and api.synthesize.call_count == 1
        new_root = root / "custom-shared"
        w.shared_audio_root.setText(str(new_root)); w.save_shared_audio_root()
        report["changing_root_saves_old_draft_then_loads_new_library"] = len(load_dialogues(dict(dialogue_file=str(library)))) == 110 and len(w.edit_dialogues) == 38 and shared_root(store) == new_root
        w.edit_dialogues[0]["text"] = "你认真生活的样子，我希望你自己也能看见。"
        expected = w.edit_dialogues[0]["text"]
        w.render_dialogues(); w.add_profile()
        profile = store.profile(w.editing_id)
        report["first_binding_preserves_unsaved_shared_edits"] = profile is not None and load_dialogues(profile)[0]["text"] == expected and profile["dialogues"][0]["text"] == expected
        bad = root / "bad-shared"; bad.mkdir(); badfile = bad / "dialogues.json"; badfile.write_text("broken json", encoding="utf-8")
        badstore = Store(root / "bad/config.json"); badstore.config["shared_asset_dir"] = str(bad)
        with patch.object(Window, "report_error", side_effect=errors.append):
            broken = Window(badstore, hooks=False)
            report["corrupt_shared_library_is_not_overwritten"] = not broken.save_dialogue_library() and badfile.read_text(encoding="utf-8") == "broken json"
            broken.cleanup(); shiboken6.delete(broken)
        assert len(errors) == 2
        errors.clear()
        report["only_mock_backend_used_no_real_api_started"] = not api.ensure.called and api.synthesize.call_count == 1
        report["no_unexpected_ui_errors"] = not errors
        print(json.dumps(report), flush=True)
        (output / "smoke-fresh-dialogues.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        w.cleanup(); app.exit(0 if all(report.values()) else 1)
    except Exception:
        import traceback
        traceback.print_exc()
        print(errors, flush=True)
        w.cleanup(); app.exit(2)

QTimer.singleShot(350, run)
QTimer.singleShot(20000, lambda: app.exit(3))
code = app.exec()
w.cleanup(); shiboken6.delete(w); api_patch.stop(); fixture.cleanup()
sys.exit(code)
