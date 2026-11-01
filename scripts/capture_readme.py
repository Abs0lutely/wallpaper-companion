"""Capture real application widgets using disposable, clearly labeled demo data."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
(ROOT / "output").mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(prefix="readme-capture-", dir=ROOT / "output")
root = Path(fixture.name)
os.environ.update(WALLPAPER_COMPANION_DATA=str(root / "data"), GPT_SOVITS_DIR="")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from companion import paths
from companion.core import Store, new_profile
from companion.assets import attach_resources
from companion.dialogues import dialogue_rules
from companion.ui import Window, STYLE
import shiboken6

destination = ROOT / "readme-assets"
destination.mkdir(exist_ok=True)
store = Store(root / "data/config.json")
profile = new_profile("雨落在窗边 · 演示")
profile.update(dialogues=json.loads((ROOT / "examples/dialogues/heartfelt-zh-CN.json").read_text(encoding="utf-8")),
               rules=dialogue_rules(), bgm_enabled=True, original_audio_policy="allow")
profile = attach_resources(profile, root / "shared")
store.config.update(profiles=[profile], manual_profile=profile["id"], we_dir="", workshop_dir="", hover_help=False,
                    operation_voice_enabled=False)
store.save()
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
app.setStyle("Fusion"); app.setStyleSheet(STYLE)
with ExitStack() as stack:
    stack.enter_context(patch.object(Window, "detect"))
    stack.enter_context(patch.object(Window, "scan_library"))
    stack.enter_context(patch("companion.managed_api.api"))
    stack.enter_context(patch("companion.secrets.read_secret", return_value=""))
    stack.enter_context(patch.object(paths, "discover_wallpaper_engine", return_value=("", "")))
    w = Window(store, hooks=False)
    w.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)
    w.poll.stop(); w.tick.stop(); w.resize(1280, 900)
    w.current_display_text = "当前壁纸 · 雨落在窗边\n演示配置，不连接真实壁纸"
    w.refresh_status()
    w.show(); QTest.qWait(200)
    def shot(name):
        app.processEvents(); QTest.qWait(100)
        assert w.grab().save(str(destination / name))
    try:
        shot("home.png")
        w.navigation[5].click(); shot("dialogues.png")
        w.show_home_section(1); shot("rules.png")
    finally:
        w.cleanup(); shiboken6.delete(w)
fixture.cleanup()
print("Captured home, dialogues and rules from real UI with demo-only data.")
