"""Native redesign workflow with a disposable Store; no real API or wallpaper edits."""
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from companion.appearance import PINK, background_path
from companion.core import ROOT, Store, new_profile
from companion.ui import Window

output = ROOT / "output"; output.mkdir(exist_ok=True)
app = QApplication([]); app.setStyle("Fusion")
app.setQuitOnLastWindowClosed(False)
report = {}


def wait(predicate):
    deadline = time.monotonic() + 8
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError("UI workflow timed out")
        QTest.qWait(30)


with tempfile.TemporaryDirectory(dir=output) as tmp, \
        patch("companion.ui.foreground_state", return_value=dict(desktop=True, fullscreen=False, own=False)), \
        patch("companion.managed_api.api"):
    root = Path(tmp).resolve()
    store = Store(root / "data/config.json")
    active = new_profile("樱花落下的午后")
    other = new_profile("雨夜书房")
    active.update(bgm_enabled=False, original_audio_policy="allow", fullscreen_mute=False)
    store.config.update(profiles=[active, other], manual_profile=active["id"])
    store.save()
    w = Window(store, hooks=False)
    w.resize(1280, 940)
    w.poll.stop()
    errors = []
    w.report_error = errors.append
    w.show()
    QTest.qWait(300)
    w.tick.stop(); w.poll.stop()
    try:
        report["navigation_preserves_all_pages"] = w.tabs.count() == 8 and not w.tabs.tabBar().isVisible()
        for index, nav in w.navigation.items():
            nav.click(); app.processEvents()
            assert w.tabs.currentIndex() == index
        w.show_home_section(2)
        report["resource_section"] = w.tabs.currentIndex() == 0 and w.profile_sections.currentIndex() == 1 and w.voice_dir.isVisible()
        w.show_home_section(1)
        report["rule_section"] = w.rules_table.isVisible()
        w.show_home_section(0)
        report["sound_section"] = w.voice_volume.isVisible() and not w.voice_dir.isVisible()

        source = root / "blue.png"
        image = QImage(300, 200, QImage.Format.Format_RGB32); image.fill(QColor("#286acb")); assert image.save(str(source))
        w.import_background(source)
        wait(lambda: not w.background_busy)
        report["background_import_updates_native_theme"] = not errors and store.config["appearance"]["accent"] != PINK and not w.hero.image.isNull()
        managed = background_path(store)
        source.unlink()
        report["import_copies_source"] = managed.is_file()
        w.auto_color.setChecked(False)
        report["fixed_pink_persisted"] = not Store(store.path).config["appearance"]["auto_color"] and PINK in w.styleSheet()
        w.auto_color.setChecked(True)
        report["auto_color_restored"] = store.config["appearance"]["accent"] in w.styleSheet()
        old_preferences = store.config["appearance"].copy()
        bad = root / "broken.png"; bad.write_bytes(b"broken")
        w.import_background(bad); wait(lambda: not w.background_busy)
        report["invalid_import_preserves_previous"] = bool(errors) and store.config["appearance"] == old_preferences
        errors.clear()
        with patch.object(store, "save", side_effect=OSError("fixture save failure")):
            w.auto_color.setChecked(False)
        report["failed_appearance_save_rolls_back"] = errors and store.config["appearance"] == old_preferences and w.auto_color.isChecked()
        errors.clear()

        w.manual.setChecked(False)
        w.current = dict(path="", title="隔离测试", running=True)
        active["wallpaper"] = "fixture-active"
        w.current["path"] = "fixture-active"
        # The fixture changes the binding directly; keep the editor in sync so
        # the next selection tests editing/playing, rather than an unsaved prompt.
        w.wallpaper_path.setText(active["wallpaper"])
        w.activate_profile(force=True)
        w.refresh_profiles(other["id"])
        app.processEvents()
        report["editing_and_playing_are_distinct"] = w.active_id == active["id"] and w.editing_id == other["id"] and "当前播放" in w.editing_context.text()
        w.player_volume.setValue(43)
        w.commit_player_volume()
        reopened = Store(store.path)
        report["player_volume_targets_active_profile"] = reopened.profile(active["id"])["bgm_volume"] == 43 and reopened.profile(other["id"])["bgm_volume"] == 25 and w.bgm_volume.value() == 25
        with patch.object(store, "save", side_effect=OSError("fixture volume failure")):
            w.player_volume.setValue(61); w.commit_player_volume()
        report["failed_volume_save_rolls_back"] = errors and active["bgm_volume"] == 43 and w.player_volume.value() == 43
        errors.clear()
        w.refresh_profiles(active["id"]); app.processEvents()
        w.profile_name.setText("未保存的名称")
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            w.profile_picker.setCurrentIndex(1)
        report["canceled_profile_switch_restores_picker"] = w.editing_id == active["id"] and w.profile_picker.currentData() == active["id"]
        w.profile_name.setText(active["name"])
        w.resize(1100, 780); app.processEvents()
        report["long_pages_do_not_force_oversized_window"] = w.width() <= 1100 and w.height() <= 780
        w.resize(1280, 900); app.processEvents()

        # Optional local artwork is only used in this disposable screenshot fixture.
        if len(sys.argv) > 1:
            w.import_background(Path(sys.argv[1])); wait(lambda: not w.background_busy)
        w.current_display_text = "樱花落下的午后"
        w.render_current_wallpaper()
        w.refresh_shell()
        app.processEvents()
        assert w.grab().save(str(output / "ui-redesign-home.png"))
        w.show_home_section(2); app.processEvents()
        assert w.grab().save(str(output / "ui-redesign-resources.png"))
        w.tabs.setCurrentIndex(3); app.processEvents()
        assert w.grab().save(str(output / "ui-redesign-settings.png"))
        settings = store.config["appearance"].copy()
        w.cleanup(); w.hide()
        second = Window(Store(store.path), hooks=False)
        second.poll.stop(); second.tick.stop(); second.show(); app.processEvents()
        report["reopen_restores_art_and_theme"] = not second.hero.image.isNull() and second.store.config["appearance"] == settings
        second.reset_appearance()
        report["reset_keeps_copied_art"] = background_path(second.store) is None and second.hero.image.isNull() and managed.exists()
        second.cleanup(); second.hide()
        report["no_unexpected_errors"] = not errors
        (output / "smoke-redesign.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        assert all(report.values()), report
    finally:
        w.cleanup(); w.hide()
app.quit()
