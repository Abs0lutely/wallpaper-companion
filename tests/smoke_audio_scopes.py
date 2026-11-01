"""Shared/legacy scope unions and cell-vs-header hover content on native Qt."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from companion.assets import shared_root
from companion.core import ROOT, Store, new_profile
from companion.ui import Window
import shiboken6

app = QApplication([]); app.setQuitOnLastWindowClosed(False)
output = ROOT / "output"; output.mkdir(exist_ok=True); report = {}
with tempfile.TemporaryDirectory(dir=output) as tmp:
    store = Store(Path(tmp)/"data/config.json")
    root = shared_root(store); legacy = store.path.parent/"audio/shared"
    for p in [root/"voice/新目录声音.wav", legacy/"voice/旧目录声音.wav", legacy/"bgm/完整音乐文件名.wav"]:
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"test inventory only")
    p = new_profile("共同使用旧共享目录")
    p.update(voice_dir=str(legacy/"voice"),bgm_dir=str(legacy/"bgm"))
    store.config.update(profiles=[p],we_dir="",workshop_dir=""); store.save()
    w = Window(store,hooks=False); w.show(); w.tabs.setCurrentIndex(6)
    def wait():
        end = time.monotonic()+6
        while w.audio_library_busy or w.audio_refresh_pending:
            assert time.monotonic()<end
            QTest.qWait(20)
    try:
        wait()
        w.audio_scope.setCurrentIndex(w.audio_scope.findData("shared:voice")); wait()
        report["shared_voice_includes_current_and_legacy_roots"] = {r["name"] for r in w.audio_records} == {"新目录声音.wav","旧目录声音.wav"}
        w.audio_scope.setCurrentIndex(w.audio_scope.findData("shared:bgm")); wait()
        report["shared_bgm_finds_legacy_music"] = len(w.audio_records)==1 and w.audio_records[0]["name"] == "完整音乐文件名.wav"
        report["scope_does_not_rewrite_user_config"] = Store(store.path).config["shared_asset_dir"] == "" and Store(store.path).profile(p["id"])["voice_dir"] == str(legacy/"voice")
        app.processEvents()
        table = w.audio_table; viewport = table.viewport()
        def hover(column):
            point = viewport.mapToGlobal(table.visualItemRect(table.item(0,column)).center())
            with patch("companion.help_ui.QCursor.pos",return_value=point), patch("companion.help_ui.QApplication.widgetAt",return_value=viewport), patch("companion.help_ui.QToolTip.showText") as shown:
                QApplication.sendEvent(viewport,QEvent(QEvent.Type.Enter)); w.hover_help.show_pending()
                return shown.call_args.args[1] if shown.called else ""
        report["filename_hover_shows_complete_filename"] = hover(0) == "完整音乐文件名.wav"
        report["usage_hover_shows_label_and_actual_directory"] = "共享" in hover(1) and str((legacy/"bgm").resolve()) in hover(1)
        report["size_hover_includes_exact_bytes"] = f"{len(b'test inventory only')} 字节" in hover(3)
        header = table.horizontalHeader()
        point = header.mapToGlobal(QPoint(header.sectionViewportPosition(0)+15,10))
        detail = w.hover_help.table_detail(header.viewport(),point)
        report["only_header_hover_describes_column_function"] = detail[-1] == table.horizontalHeaderItem(0).toolTip() and "双击" in detail[-1]
        w.hover_help.set_enabled(False)
        report["switch_off_clears_pending_cell_detail"] = not w.hover_help.timer.isActive() and w.hover_help.detail is None
    finally:
        w.cleanup(); shiboken6.delete(w)
(output/"smoke-audio-scopes.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report)); sys.exit(0 if all(report.values()) else 1)
