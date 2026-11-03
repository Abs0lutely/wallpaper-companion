"""Native update UI lifecycle, using isolated data and an in-process release service."""
import json
import sys
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
import shiboken6
from companion.core import ROOT, Store
from companion.i18n import set_language
from companion.runtime import LAYOUT
from companion.ui import Window
from companion.updates_ui import UpdateController
from test_updates import release_payload, Session
from companion.updates import API_URL, ReleaseClient, parse_release


def wait_until(predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline: QTest.qWait(20)
    assert predicate(), "Timed out waiting for update UI"


app = QApplication([]); app.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory(dir=ROOT / "output", prefix="updates-ui-") as tmp:
    root = Path(tmp)
    for locale in ("zh-CN", "en-US"):
        set_language(locale)
        store = Store(root / locale / "data/config.json")
        store.config.update(run_mode="standalone", operation_voice_enabled=False)
        store.save()
        w = Window(store, hooks=False); w.poll.stop(); w.tick.stop(); w.show()
        try:
            w.updates.close()
            target = root / locale / "installed app"; target.mkdir(parents=True)
            (target / "WallpaperCompanion.exe").write_bytes(b"old exe")
            (target / "WallpaperCompanionUpdater.exe").write_bytes(b"fake helper")
            (target / "app-version.txt").write_text("0.11.0")
            payload = release_payload()
            release = parse_release(payload, "0.11.0", False)
            import hashlib
            sums = (hashlib.sha256(b"installer").hexdigest() + "  " + release.name).encode()
            session = Session({API_URL: json.dumps(payload).encode(), release.url: b"installer", release.checksum_url: sums})
            controller = w.updates = UpdateController(w, layout=replace(LAYOUT, app_dir=target, frozen=True, portable=False),
                                                       client_factory=lambda: ReleaseClient(session))
            # Original slot belongs to the now-closed controller; reconnect for this fixture.
            w.auto_update_enabled.toggled.disconnect()
            w.auto_update_enabled.toggled.connect(controller.preference_changed)
            controller.check()
            wait_until(lambda: controller.cancel is None)
            assert controller.download and controller.install_button.isEnabled()
            assert controller.dialog.isVisible() and controller.notes.toPlainText() == "Release notes"
            assert ("已就绪" if locale == "zh-CN" else "ready") in w.update_status.text()
            before = store.path.read_bytes()
            with patch("companion.updates_ui.subprocess.Popen") as launch, patch.object(w.autosave, "flush", return_value=False), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                controller.install(); launch.assert_not_called()
            assert store.path.read_bytes() == before and not w.quitting
            with patch("companion.updates_ui.subprocess.Popen") as launch, patch.object(QMessageBox, "information"):
                w.tts_busy = True; controller.install(); launch.assert_not_called(); w.tts_busy = False
                w.api_busy = True; controller.install(); launch.assert_not_called(); w.api_busy = False
            # Disabling is persisted and undo restores both the setting and the scheduler.
            controller.dialog.hide()
            w.auto_update_enabled.setChecked(False)
            assert Store(store.path).config["auto_update_enabled"] is False
            assert not controller.timer.isActive()
            assert w.autosave.undo()
            assert Store(store.path).config["auto_update_enabled"] is True and controller.timer.isActive()
            # Saving failures cannot leave a falsely saved checkbox or cancel useful work.
            with patch.object(store, "save", side_effect=OSError("disk full")), patch.object(w, "report_error"):
                w.auto_update_enabled.setChecked(False)
            assert w.auto_update_enabled.isChecked() and store.config["auto_update_enabled"] is True
            # Background cancellation leaves manual checking available.
            controller.cancel = threading.Event(); controller.manual = False
            store.config["auto_update_enabled"] = False; controller.sync()
            assert controller.cancel.is_set(); controller.cancel = None
            controller.check(manual=True)
            assert controller.dialog.isVisible()
            # Cached download remains usable after opting out, but still requires confirmation.
            with patch("companion.updates_ui.subprocess.Popen") as launch, patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), patch("companion.program_update.running_instances", return_value=[]), patch.object(w, "cleanup") as cleanup:
                # Do not call install here: QApplication.quit is an explicit terminal action.
                helper, plan = controller.prepare_handoff()
                assert helper.is_file() and json.loads(plan.read_text(encoding="utf-8"))["target"] == str(target)
                launch.assert_not_called(); cleanup.assert_not_called()
            assert not w.quitting
            print(locale + ": verified download / bilingual dialog / busy guard / save failure / opt-out / undo / isolated handoff PASS")
        finally:
            w.cleanup(); shiboken6.delete(w)
set_language("zh-CN")
