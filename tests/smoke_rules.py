"""Native grouped rule editor, key recording and portable preset workflows."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from companion.core import ROOT, Store, new_profile, new_rule
from companion.ui import Window, RuleDialog, STYLE
from companion.presets import export_payload

output = ROOT / "output"
output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
root = Path(fixture.name)
store = Store(root / "data/config.json")
profile = new_profile("本机配置")
profile["voice_dir"] = str(root / "voice")
Path(profile["voice_dir"]).mkdir()
store.config["profiles"] = [profile]
store.save()
app = QApplication([]); app.setStyle("Fusion"); app.setStyleSheet(STYLE)
w = Window(store, hooks=False); w.show(); app.processEvents()
report = {}
try:
    w.edit_dialogues.append(dict(id="custom-category", category="我的专属分类", text="测试文本", enabled=True))
    dialog = RuleDialog(parent=w)
    report["categories_follow_library_without_free_typing"] = dialog.source_category.findText("我的专属分类") >= 0 and not dialog.source_category.isEditable()
    w.edit_dialogues.pop()
    dialog.show(); app.processEvents()
    dialog.event_family.setCurrentIndex(dialog.event_family.findData("mouse"))
    dialog.mouse_action.setCurrentIndex(dialog.mouse_action.findData("mouse_right"))
    app.processEvents()
    report["mouse_hides_keyboard_and_random"] = not dialog.hotkey.isVisible() and not dialog.interval_row.isVisible() and dialog.mouse_action.isVisible()
    dialog.source_mode.setCurrentIndex(dialog.source_mode.findData("category"))
    dialog.source_category.setCurrentText("点击回应")
    dialog.accept()
    report["mouse_rule_saved"] = dialog.rule["event"] == "mouse_right" and dialog.rule["source"] == "点击回应"
    keyboard = RuleDialog(parent=w)
    keyboard.show(); app.processEvents()
    keyboard.event_family.setCurrentIndex(keyboard.event_family.findData("keyboard"))
    keyboard.record_button.click()
    QTest.keyClick(keyboard.record_button, Qt.Key.Key_H, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    report["combo_recorded_without_typing_syntax"] = keyboard._binding == "<ctrl>+<alt>+h" and not keyboard._recording and "CTRL" not in keyboard.hotkey.text()
    previous = keyboard._binding
    keyboard.record_button.click(); QTest.keyClick(keyboard.record_button, Qt.Key.Key_Escape)
    report["escape_cancels_recording"] = keyboard._binding == previous and not keyboard._recording
    keyboard.accept()
    report["keyboard_rule_saved"] = keyboard.rule["hotkey"] == "<ctrl>+<alt>+h" and keyboard.rule["event"] == "key"
    modifier = RuleDialog(parent=w); modifier.show(); app.processEvents()
    modifier.record_button.click(); QTest.keyClick(modifier.record_button, Qt.Key.Key_Shift)
    report["single_modifier_recorded"] = modifier._binding == "<shift>" and not modifier._recording
    modifier.close()
    enter = RuleDialog(parent=w); enter.show(); app.processEvents()
    enter.record_button.click(); QTest.keyClick(enter.record_button, Qt.Key.Key_Return)
    report["enter_recorded_without_submitting_dialog"] = enter._binding == "<enter>" and enter.result() != enter.DialogCode.Accepted
    enter.close()
    duplicate = RuleDialog(parent=w, existing_rules=[keyboard.rule]); duplicate.show(); app.processEvents()
    duplicate._binding = "<alt>+<ctrl>+h"
    with patch.object(QMessageBox, "warning") as warning:
        duplicate.accept()
        report["duplicate_combo_rejected"] = warning.called and duplicate.result() != duplicate.DialogCode.Accepted
    duplicate.close()
    scheduled = RuleDialog(parent=w)
    scheduled.show(); app.processEvents()
    scheduled.trigger_category.setCurrentIndex(scheduled.trigger_category.findData("time"))
    scheduled.time_mode.setCurrentIndex(scheduled.time_mode.findData("scheduled"))
    scheduled.at.setTime(QTime(8, 30)); app.processEvents()
    report["fixed_time_shows_only_relevant_fields"] = scheduled.at.isVisible() and not scheduled.event_family.isVisible() and not scheduled.interval_row.isVisible()
    scheduled.grab().save(str(output / "rule-scheduled.png"))
    scheduled.accept()
    report["fixed_time_saved"] = scheduled.rule["event"] == "scheduled" and scheduled.rule["at"] == "08:30"
    edited = new_profile("分享给朋友")
    edited["rules"] = [dialog.rule, keyboard.rule, scheduled.rule]
    payload, _ = export_payload([edited])
    imported = w.apply_interaction_preset(payload)
    new = store.profile(imported["profile_ids"][0])
    report["import_includes_rules_and_dialogues"] = len(new["rules"]) == 3 and len(new["dialogues"]) == 38 and not new["wallpaper"]
    path = root / "share.json"
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(path), "")):
        w.export_interaction_preset()
    report["export_button_writes_portable_file"] = path.is_file() and "wallpaper-companion-preset" in path.read_text(encoding="utf-8") and str(root) not in path.read_text(encoding="utf-8")
    before = len(store.config["profiles"])
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(path), "")), patch("companion.presets_ui.PresetImportDialog.exec", return_value=1):
        w.import_interaction_preset()
    report["import_button_flow_creates_configuration"] = len(store.config["profiles"]) == before + 1
    mouse_preview = RuleDialog(dialog.rule, w); mouse_preview.show(); app.processEvents()
    mouse_preview.grab().save(str(output / "rule-mouse.png")); mouse_preview.close()
    key_preview = RuleDialog(keyboard.rule, w); key_preview.show(); app.processEvents()
    key_preview.grab().save(str(output / "rule-keyboard.png")); key_preview.close()
    (output / "smoke-rules.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
finally:
    w.cleanup()
    import shiboken6
    shiboken6.delete(w)
    fixture.cleanup()
sys.exit(0 if all(report.values()) else 1)
