"""Real navigation, reversible saves and failure protection in disposable data."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from companion.assets import attach_resources, shared_root
from companion.core import ROOT, Store, new_profile, new_rule
from companion.ui import Window
import shiboken6

app = QApplication([]); app.setQuitOnLastWindowClosed(False)
output = ROOT / "output"; output.mkdir(exist_ok=True)
report = {}; errors = []
with tempfile.TemporaryDirectory(dir=output) as tmp, patch("companion.managed_api.api"), patch("companion.secrets.read_secret", return_value=""), patch("companion.secrets.write_secret"):
    store = Store(Path(tmp) / "data/config.json")
    one = attach_resources(new_profile("一"), shared_root(store))
    two = attach_resources(new_profile("二"), shared_root(store))
    store.config.update(profiles=[one, two], we_dir="", workshop_dir="")
    store.save()
    w = Window(store, hooks=False); w.show(); w.report_error = errors.append
    try:
        w.tabs.setCurrentIndex(1)
        count = len(one["rules"])
        w.edit_rules.append(new_rule("mouse_middle", "自动保存测试")); w.render_rules()
        w.tabs.setCurrentIndex(5)
        report["leaving_rules_saves_to_disk"] = len(Store(store.path).profile(one["id"])["rules"]) == count + 1
        report["toast_has_real_undo_button"] = w.autosave.toast.isVisible() and w.autosave.undo_button.isEnabled()
        w.grab().save(str(output / "autosave-toast.png"))
        w.autosave.undo_button.click()
        report["undo_restores_saved_rule_and_ui"] = len(Store(store.path).profile(one["id"])["rules"]) == count and len(w.edit_rules) == count
        file = Path(one["dialogue_file"])
        original_file = file.read_bytes() if file.exists() else None
        w.edit_dialogues[0]["text"] = "共享台词自动保存测试"
        w.render_dialogues(); w.tabs.setCurrentIndex(1)
        file = Path(one["dialogue_file"])
        report["linked_dialogue_save_updates_all_references"] = file.exists() and all(p["dialogues"][0]["text"] == "共享台词自动保存测试" for p in Store(store.path).config["profiles"])
        saved_file = file.read_bytes()
        file.write_bytes(saved_file + b"\n")
        report["undo_refuses_external_shared_file_change"] = not w.autosave.undo() and file.read_bytes() == saved_file + b"\n"
        errors.clear(); file.write_bytes(saved_file)
        report["undo_restores_shared_file_and_all_profiles"] = w.autosave.undo() and (file.read_bytes() if file.exists() else None) == original_file and all(p["dialogues"][0]["text"] != "共享台词自动保存测试" for p in Store(store.path).config["profiles"])
        w.profile_name.setText("切换前保存")
        w.profiles.setCurrentRow(1)
        report["profile_switch_autosaves_previous"] = Store(store.path).profile(one["id"])["name"] == "切换前保存" and w.editing_id == two["id"] and w.profiles.currentRow() == 1
        w.tabs.setCurrentIndex(3); w.poll_seconds.setValue(11); w.tabs.setCurrentIndex(0)
        report["settings_navigation_autosave"] = Store(store.path).config["poll_seconds"] == 11
        report["settings_undo_updates_timer"] = w.autosave.undo() and w.poll_seconds.value() == 4 and w.poll.interval() == 4000
        old = copy.deepcopy(store.config); disk = store.path.read_bytes()
        w.voice_dir.setText(str(Path(tmp) / "does-not-exist"))
        page = w.tabs.currentIndex(); w.tabs.setCurrentIndex(1)
        report["invalid_draft_blocks_navigation_without_loss"] = w.tabs.currentIndex() == page and w.voice_dir.text().endswith("does-not-exist") and store.config == old and store.path.read_bytes() == disk
        section = w.profile_sections.currentIndex(); w.profile_sections.setCurrentIndex(1 - section)
        report["invalid_draft_blocks_inner_section_navigation"] = w.profile_sections.currentIndex() == section
        errors.clear(); w.voice_dir.setText(old["profiles"][1]["voice_dir"])
        w.profile_name.setText("失败仍保留")
        with patch.object(store, "save", side_effect=OSError("fixture denied")):
            report["failed_write_keeps_config_and_draft"] = not w.autosave.flush() and store.config == old and store.path.read_bytes() == disk and w.profile_name.text() == "失败仍保留"
        errors.clear(); w.profile_name.setText(old["profiles"][1]["name"])
        w.voice_volume.setValue(43); assert w.autosave.flush()
        w.profile_name.setText("后续未保存草稿")
        report["undo_never_overwrites_new_draft"] = not w.autosave.undo() and w.profile_name.text() == "后续未保存草稿"
        errors.clear(); w.profile_name.setText(store.profile(two["id"])["name"])
        resource = store.profile(two["id"])["voice_dir"]
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            w.restore_defaults()
        report["reset_preserves_resources_and_bindings"] = len(store.config["profiles"]) == 2 and store.profile(two["id"])["voice_dir"] == resource and w.voice_volume.value() == 80
        report["reset_can_be_undone"] = w.autosave.undo() and w.voice_volume.value() == 43
        w.autosave.timer.start(20); QTest.qWait(200)
        report["toast_dismisses_itself"] = not w.autosave.toast.isVisible()
        report["no_unexpected_errors"] = not errors
    finally:
        w.cleanup(); shiboken6.delete(w)
(output / "smoke-autosave.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report)); sys.exit(0 if all(report.values()) else 1)
