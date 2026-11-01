"""Transfer classification and duplicate confirmation with a real modal and fake TTS."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import wave
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from companion.assets import shared_root
from companion.core import ROOT, Store, filename_for
from companion.ui import Window
import shiboken6

app = QApplication([]); app.setQuitOnLastWindowClosed(False)
out = ROOT / "output"; out.mkdir(exist_ok=True)
report = {}; errors = []
stream = io.BytesIO()
with wave.open(stream, "wb") as f:
    f.setparams((1, 2, 16000, 0, "NONE", "not compressed")); f.writeframes(b"\x01\x00" * 1600)
data = stream.getvalue()
with tempfile.TemporaryDirectory(dir=out) as tmp, patch("companion.managed_api.api") as api, patch("companion.secrets.read_secret", return_value=""), patch("companion.secrets.write_secret"):
    api.synthesize.return_value = data
    store = Store(Path(tmp)/"data/config.json"); store.config.update(we_dir="", workshop_dir="")
    w = Window(store, hooks=False); w.report_error = errors.append; w.show()
    w.filename_model.setText("模型A")
    def wait(predicate):
        deadline = time.monotonic()+7
        while not predicate():
            assert time.monotonic() < deadline, "duplicate review timed out"
            QTest.qWait(20)
    def choose(title):
        deadline = time.monotonic()+6
        def click():
            for dialog in w.findChildren(QMessageBox):
                if dialog.isVisible() and dialog.windowTitle() == "发现同名音频":
                    next(b for b in dialog.buttons() if b.text() == title).click()
                    return
            assert time.monotonic() < deadline, "confirmation dialog missing"
            QTimer.singleShot(20, click)
        QTimer.singleShot(20, click)
    try:
        w.edit_dialogues = [dict(id="a",category="早晨",text="已有音频",enabled=True),dict(id="b",category="夜间",text="新音频",enabled=True)]
        w.render_dialogues(); w.select_dialogues("all")
        root = shared_root(store)/"voice"; existing = root/"早晨"/filename_for("已有音频")
        existing.parent.mkdir(parents=True); existing.write_bytes(data)
        w.skip_existing_dialogue_audio.setChecked(True); w.send_dialogues_to_tts()
        report["transfer_keeps_categories_and_skip_preference"] = w.skip_existing_tts_audio.isChecked() and w.transferred_dialogues[0]["category"] == "早晨"
        choose("取消"); w.generate_audio(); wait(lambda:not w.tts_busy)
        report["cancel_never_synthesizes_or_changes_existing_audio"] = not api.synthesize.called and existing.read_bytes() == data and len(list(root.rglob("*.wav"))) == 1
        choose("跳过重复，生成其余"); w.generate_audio(); wait(lambda:not w.tts_busy)
        report["skip_generates_only_missing_in_original_category"] = api.synthesize.call_count == 1 and (root/"夜间"/filename_for("新音频","模型A")).is_file() and existing.read_bytes() == data
        before = api.synthesize.call_count
        choose("跳过重复，生成其余"); w.generate_audio(); wait(lambda:not w.tts_busy)
        report["all_existing_skips_without_api_work"] = api.synthesize.call_count == before and "跳过 2" in w.tts_status.text()
        choose("全部生成，另存副本"); w.generate_audio(); wait(lambda:not w.tts_busy)
        report["explicit_regeneration_preserves_original_files"] = api.synthesize.call_count == before+2 and len(list(root.rglob("*.wav"))) == 4 and existing.read_bytes() == data
        report["no_user_api_started_and_no_ui_errors"] = not api.start.called and not api.ensure.called and not errors
    finally:
        w.cleanup(); shiboken6.delete(w)
(out/"smoke-duplicate-generation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report)); sys.exit(0 if all(report.values()) else 1)
