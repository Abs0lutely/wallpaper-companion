"""Hover delay, global switch, dynamic provider and dialog help checks."""
import json
import sys
import tempfile
import weakref
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QPoint, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from companion.core import ROOT, Store
from companion.ui import Window, RuleDialog, STYLE

output = ROOT / "output"
output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
store = Store(Path(fixture.name) / "config.json")
app = QApplication([])
app.setStyle("Fusion"); app.setStyleSheet(STYLE)
w = Window(store, hooks=False)
w.show()
# Drain native show/activation/leave events before synthesizing the hover.
# Otherwise a queued OS Leave can cancel the timer after our synthetic Enter.
assert QTest.qWaitForWindowExposed(w, 5000)
QTest.qWait(250)
report = {}
try:
    report["default_help_enabled"] = w.hover_help.enabled
    report["delayed_one_second"] = w.hover_help.timer.interval() == 1000
    report["field_explanation"] = "播放语音" in w.voice_dir.toolTip()
    point = w.voice_dir.mapToGlobal(QPoint(10, 10))
    with patch("companion.help_ui.QCursor.pos", return_value=point), patch("companion.help_ui.QApplication.widgetAt", return_value=w.voice_dir), patch("companion.help_ui.QToolTip.showText") as show:
        QApplication.sendEvent(w.voice_dir, QEvent(QEvent.Type.Enter))
        report["hover_starts_timer"] = w.hover_help.timer.isActive()
        for _ in range(40):
            if show.called:
                break
            QTest.qWait(50)
        report["hover_shows_explanation"] = show.called and "播放语音" in show.call_args.args[1]
        w.help_button.click()
        report["switch_off_persisted"] = not w.hover_help.enabled and not Store(store.path).config["hover_help"]
        show.reset_mock()
        QApplication.sendEvent(w.voice_dir, QEvent(QEvent.Type.Enter))
        w.hover_help.target = weakref.ref(w.voice_dir)
        w.hover_help.show_pending()
        report["off_suppresses_tooltips"] = not show.called and not w.hover_help.timer.isActive()
        w.help_button.click()
        report["switch_on_persisted"] = w.hover_help.enabled and Store(store.path).config["hover_help"]
    w.provider_choice.setCurrentIndex(w.provider_choice.findData("azure_speech"))
    report["dynamic_fields_have_help"] = bool(w.provider_widgets["api_key"].toolTip()) and bool(w.provider_widgets["voice"].toolTip())
    dialog = RuleDialog(parent=w)
    dialog.show(); app.processEvents()
    report["dialog_fields_have_help"] = "录制" in dialog.hotkey.toolTip() and "最短" in dialog.low.toolTip()
    dialog.close()
    report["user_guide_exists"] = (ROOT / "USER_GUIDE.md").is_file()
    manual = next(b for b in w.findChildren(QPushButton) if b.text() == "打开使用手册")
    with patch("companion.documents_ui.QDesktopServices.openUrl") as external:
        manual.click(); app.processEvents()
        viewer = w.document_viewer
        report["manual_button_opens_in_app"] = viewer.isVisible() and "功能和输入框使用手册" in viewer.browser.toPlainText()
        viewer.grab().save(str(output / "manual-window.png"))
        report["manual_does_not_need_md_association"] = not external.called
        viewer.follow_link(QUrl("BUILDING.md")); app.processEvents()
        report["manual_local_links_work"] = viewer.current_path == ROOT / "BUILDING.md" and "自行构建" in viewer.browser.toPlainText()
        viewer.close(); manual.click(); app.processEvents()
        report["manual_reopens_same_window"] = w.document_viewer is viewer and viewer.current_path == ROOT / "USER_GUIDE.md" and viewer.isVisible()
        with patch("companion.documents_ui.QMessageBox.warning") as warning:
            viewer.follow_link(QUrl("missing-document.md"))
            report["missing_manual_link_reports_error"] = warning.called and viewer.current_path == ROOT / "USER_GUIDE.md"
        viewer.close()
    w.tabs.setCurrentIndex(0)
    app.processEvents(); w.grab().save(str(output / "help-toggle.png"))
    (output / "smoke-help.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
finally:
    w.cleanup()
    import shiboken6
    shiboken6.delete(w)
    fixture.cleanup()
sys.exit(0 if all(report.values()) else 1)
