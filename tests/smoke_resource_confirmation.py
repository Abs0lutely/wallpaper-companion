"""Exercise dedicated-directory cancellation and real QMessageBox Yes/No buttons."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from companion.assets import attach_resources, private_root, shared_root
from companion.core import ROOT, Store, new_profile
from companion.resources_ui import ResourceDialog
from companion.ui import STYLE, Window

output = ROOT / "output"
output.mkdir(exist_ok=True)
app = QApplication([]); app.setStyle("Fusion"); app.setStyleSheet(STYLE)
report, errors = {}, []
with tempfile.TemporaryDirectory(dir=output) as temp, patch("companion.managed_api.api"):
    root = Path(temp)
    store = Store(root / "data/config.json")
    p = attach_resources(new_profile("二次确认测试"), shared_root(store))
    store.config["profiles"] = [p]
    store.save()
    original = store.path.read_bytes()
    (Path(p["voice_dir"]) / "保留.wav").write_bytes(b"unchanged")
    w = Window(store, hooks=False)
    w.show(); app.processEvents()
    w.refresh_profiles(p["id"])
    w.report_error = errors.append
    try:
        with patch.object(ResourceDialog, "exec", return_value=QDialog.DialogCode.Rejected), patch.object(QMessageBox, "question") as question:
            w.make_audio_dirs()
            report["settings_cancel_has_no_confirmation_or_write"] = not question.called and store.path.read_bytes() == original and not private_root(store, p).exists()

        def answer(value, screenshot=False):
            def click():
                box = app.activeModalWidget()
                try:
                    assert isinstance(box, QMessageBox)
                    report["default_answer_is_no"] = box.defaultButton() == box.button(QMessageBox.StandardButton.No)
                    report["summary_has_profile_and_paths"] = p["name"] in box.text() and str(private_root(store, p)) in box.text()
                    if screenshot:
                        box.grab().save(str(output / "resource-confirmation.png"))
                    QTest.mouseClick(box.button(value), Qt.MouseButton.LeftButton)
                except Exception as exc:
                    errors.append(str(exc))
                    if box:
                        box.reject()
            return click

        with patch.object(ResourceDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            QTimer.singleShot(100, answer(QMessageBox.StandardButton.No, True))
            w.make_audio_dirs()
        report["confirmation_no_preserves_config_and_no_directory"] = store.path.read_bytes() == original and not private_root(store, p).exists()

        with patch.object(ResourceDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            QTimer.singleShot(100, answer(QMessageBox.StandardButton.Yes))
            w.make_audio_dirs()
        actual = Store(store.path).profile(p["id"])
        report["confirmation_yes_creates_and_saves"] = Path(actual["voice_dir"]) == private_root(store, p) / "voice" and Path(actual["voice_dir"]).is_dir() and Path(actual["dialogue_file"]).is_file()
        report["shared_original_preserved"] = (Path(p["voice_dir"]) / "保留.wav").read_bytes() == b"unchanged"
        report["no_errors"] = not errors
    finally:
        w.cleanup()
        import shiboken6
        shiboken6.delete(w)
(output / "smoke-resource-confirmation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
sys.exit(0 if all(report.values()) else 1)
