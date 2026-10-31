"""Native preset/model selection and generation snapshot with a mocked API backend."""
import io
import json
import sys
import tempfile
import time
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
from companion.core import ROOT, Store, new_profile
from companion.ui import Window, STYLE

output = ROOT / "output"; output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
root = Path(fixture.name).resolve(); project = root / "project"; project.mkdir()
(project / "api_v2.py").touch()
audio = io.BytesIO()
with wave.open(audio, "wb") as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b"\0\0" * 160)
originals = {}
for name, version in [("角色甲", "v4"), ("角色乙", "v2")]:
    folder = project / "models" / version / name; folder.mkdir(parents=True)
    for file, data in [("voice-e10.ckpt", b"model"), ("voice_e10_s100.pth", b"model"), ("参考.wav", audio.getvalue()), ("参考.lab", (name + "参考原文。").encode())]:
        path = folder / file; path.write_bytes(data); originals[path] = data
store = Store(root / "data/config.json")
store.config.update(we_dir=str(root / "no-we"), workshop_dir="")
binding = new_profile("合并兼容性壁纸", str(root / "wallpaper.mp4"))
binding.update(bgm_enabled=False, rules=[])
appearance = dict(background="", accent="#cdb8ff", auto_color=False)
store.config.update(profiles=[binding], appearance=appearance)
store.config["tts"]["project"] = str(project)
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
app.setStyle("Fusion"); app.setStyleSheet(STYLE)
patches = [patch("companion.managed_api.api"), patch("companion.secrets.read_secret", return_value=""), patch("companion.secrets.write_secret")]
api = patches[0].start(); patches[1].start(); patches[2].start()
api.synthesize.return_value = audio.getvalue()
w = Window(store, hooks=False); w.show(); w.navigation[2].click()
errors, report = [], {}
w.report_error = errors.append
deadline = time.monotonic() + 20

def fail(exc):
    import traceback
    traceback.print_exc(); print(exc, errors)
    w.cleanup(); app.exit(2)

def guard(fn):
    def run():
        try: fn()
        except Exception as exc: fail(exc)
    return run

def wait(predicate, fn):
    if predicate(): QTimer.singleShot(50, guard(fn))
    elif time.monotonic() > deadline: fail(TimeoutError("character workflow timed out"))
    else: QTimer.singleShot(50, lambda: wait(predicate, fn))

def select_pair(name, version):
    index = next(i for i in range(1, w.model_pair_choice.count()) if w.model_pair_choice.itemData(i)["name"] == name)
    w.model_pair_choice.setCurrentIndex(index)
    w.reference_choice.setCurrentText(f"models/{version}/{name}/参考.wav")
    w.choose_scanned_reference(); w.read_reference_text()

def initial():
    report["new_navigation_opens_character_generation"] = w.tabs.currentIndex() == 2 and w.character_tools.isVisible()
    report["auto_scan_models_and_pairs"] = w.model_pair_choice.count() == 3 and w.provider_widgets["gpt_weights"].count() == 3
    report["scan_does_not_select_or_start_models"] = not w.provider_widgets["gpt_weights"].currentText() and api.synthesize.call_count == 0 and api.ensure.call_count == 0
    select_pair("角色甲", "v4")
    w.provider_widgets["text_lang"].setText("zh"); w.provider_widgets["prompt_lang"].setText("zh")
    with patch.object(QInputDialog, "getText", return_value=("角色甲", True)):
        w.save_current_character()
    first = w.active_character
    select_pair("角色乙", "v2")
    w.provider_widgets["text_lang"].setText("en"); w.provider_widgets["prompt_lang"].setText("en")
    with patch.object(QInputDialog, "getText", return_value=("角色乙", True)):
        w.save_current_character(as_new=True)
    second = w.active_character
    report["saved_two_complete_characters"] = len(Store(store.path).config["tts_characters"]) == 2
    restored = Store(store.path).config
    report["preset_save_preserves_appearance_and_wallpaper_bindings"] = restored["appearance"] == appearance and restored["profiles"] == [binding]
    report["save_does_not_load_api"] = api.synthesize.call_count == 0 and api.ensure.call_count == 0
    w.character_choice.setCurrentIndex(w.character_choice.findData(first))
    report["selection_restores_models_reference_text_and_languages"] = "角色甲" in w.provider_widgets["gpt_weights"].currentText() and "角色甲" in w.provider_widgets["sovits_weights"].currentText() and "角色甲" in w.provider_widgets["reference"].text() and w.provider_widgets["prompt"].toPlainText() == "角色甲参考原文。" and w.provider_widgets["text_lang"].text() == "zh" and w.provider_widgets["prompt_lang"].text() == "zh"
    w.provider_choice.setCurrentIndex(w.provider_choice.findData("azure_speech"))
    report["cloud_provider_hides_character_tools"] = not w.character_tools.isVisible()
    w.provider_choice.setCurrentIndex(w.provider_choice.findData("gpt_sovits"))
    report["provider_switch_retains_selection"] = "角色甲" in w.provider_widgets["gpt_weights"].currentText()
    w.lines.setPlainText("角色预设测试。")
    w.tts_output.setText(str(root / "generated"))
    w.generate_audio()
    wait(lambda: not w.tts_busy, lambda: generated(first, second))

def generated(first, second):
    settings, text = api.synthesize.call_args.args
    report["generate_uses_selected_snapshot"] = api.synthesize.call_count == 1 and "角色甲" in settings["gpt_weights"] and settings["text_lang"] == "zh" and text == "角色预设测试。"
    report["audio_saved_by_dialogue_name"] = (root / "generated/角色预设测试。.wav").is_file()
    report["external_switch_permission_is_boolean"] = Store(store.path).config["tts"]["allow_external_model_switch"] is False
    # Reopen from persisted settings, without starting or loading the API.
    other = Window(Store(store.path), hooks=False)
    report["restart_restores_character_and_fields"] = other.character_choice.currentData() == first and "角色甲" in other.provider_widgets["gpt_weights"].currentText()
    other.cleanup()
    import shiboken6
    shiboken6.delete(other)
    w.resize(1280, 950); app.processEvents(); w.grab().save(str(output / "characters.png"))
    w.character_choice.setCurrentIndex(w.character_choice.findData(second))
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        w.delete_current_character()
    report["delete_only_removes_preset"] = len(Store(store.path).config["tts_characters"]) == 1 and all(path.read_bytes() == data for path, data in originals.items())
    report["no_ui_errors"] = not errors
    (output / "smoke-characters.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    w.cleanup(); app.exit(0 if all(report.values()) else 1)

QTimer.singleShot(100, lambda: wait(lambda: w.character_scan_cache is not None, initial))
QTimer.singleShot(23000, lambda: app.exit(3))
code = app.exec()
w.cleanup()
for item in reversed(patches): item.stop()
import shiboken6
shiboken6.delete(w)
fixture.cleanup()
sys.exit(code)
