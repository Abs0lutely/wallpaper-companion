"""Prepared semantic UI clips: real player, opt-out, collision and no live TTS."""
import json
from pathlib import Path
import sys
import tempfile
import time
import wave
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtTest import QTest
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QPushButton
from companion.action_lines import EVENT_LINES
from companion.core import ROOT, Store, filename_for
from companion.ui import Window
from companion.operation_rules_ui import OperationRulesDialog
from companion.operation_rules import config_payload
import shiboken6

app = QApplication([]); app.setQuitOnLastWindowClosed(False)
report = {}; output = ROOT / "output"; output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=output) as tmp, patch("companion.managed_api.api") as api:
    root = Path(tmp); clips = root / "clips"
    for event in ("save", "delete", "navigate", "change"):
        category, lines = EVENT_LINES[event]
        p = clips / category / filename_for(lines[0]); p.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(p), "wb") as f:
            f.setparams((1, 2, 16000, 0, "NONE", "not compressed")); f.writeframes(b"\x01\x00" * 16000 * 2)
    store = Store(root / "data/config.json"); store.config.update(operation_voice_dir=str(clips), we_dir="", workshop_dir=""); store.save()
    w = Window(store, hooks=False); w.show()
    def wait(predicate):
        deadline = time.monotonic() + 6
        while not predicate():
            assert time.monotonic() < deadline
            QTest.qWait(20)
    try:
        wait(lambda: not w.operation_voices.scanning)
        report["default_on_and_clips_discovered"] = w.operation_voice_enabled.isChecked() and len(w.operation_voices.clips["save"]) == 1
        w.operation_voices.request("save"); wait(lambda: w.audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        report["semantic_save_clip_actually_plays"] = "操作·保存" in w.audio.voice.source().toLocalFile()
        original = w.audio.voice.source()
        w.operation_voices.request("navigate")
        report["does_not_interrupt_playing_voice"] = w.audio.voice.source() == original
        w.audio.voice.stop(); wait(lambda: not w.audio.busy); w.operation_voices.last_play = -100
        dynamic = QPushButton("删除规则", w); dynamic.show(); app.processEvents(); dynamic.click()
        wait(lambda: w.audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        report["dynamic_button_routes_to_delete_audio"] = "操作·删除" in w.audio.voice.source().toLocalFile()
        w.operation_voice_enabled.setChecked(False)
        report["opt_out_persists_and_stops_only_owned_clip"] = not Store(store.path).config["operation_voice_enabled"] and not w.audio.busy
        w.operation_voices.last_play = -100
        with patch.object(w.audio, "play_voice") as played:
            dynamic.click(); w.operation_voices.request("save")
            report["disabled_means_silent"] = not played.called
        w.operation_voice_enabled.setChecked(True); w.audio.voice.stop(); wait(lambda: not w.audio.busy); w.operation_voices.last_play = -100
        w.tabs.setCurrentIndex(5); wait(lambda: w.audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        report["navigation_has_its_own_audio"] = "操作·切换页面" in w.audio.voice.source().toLocalFile()
        w.audio.voice.stop(); wait(lambda: not w.audio.busy); w.operation_voices.last_play = -100
        before = len(w.edit_dialogues); w.add_operation_dialogues(); w.add_operation_dialogues()
        report["operation_texts_import_once_without_forced_selection"] = len(w.edit_dialogues) == before + 52 and not w.selected_dialogues()
        report["no_api_started_or_synthesis_requested"] = not api.start.called and not api.ensure.called and not api.synthesize.called
        wallpaper_rules_before = [dict(r) for r in w.edit_rules]
        dialog = OperationRulesDialog(w)
        save_row = next(i for i,r in enumerate(dialog.payload["rules"]) if r["event"] == "save")
        from PySide6.QtCore import Qt
        dialog.table.item(save_row,0).setCheckState(Qt.CheckState.Unchecked)
        dialog.table.cellWidget(save_row,3).setValue(22)
        dialog.accept()
        report["dedicated_operation_rules_persist_separately"] = w.apply_operation_rules(dialog.result_payload) and w.edit_rules == wallpaper_rules_before and next(r for r in Store(store.path).config["operation_voice_rules"] if r["event"]=="save")["cooldown"] == 22
        wait(lambda:not w.operation_voices.scanning)
        w.audio.voice.stop(); wait(lambda:not w.audio.busy); w.operation_voices.last_play=-100
        with patch.object(w.audio,"play_voice") as played:
            w.operation_voices.request("save")
            report["per_action_disable_is_enforced"] = not played.called
        dialog.deleteLater()
        w.tabs.setCurrentIndex(3); app.processEvents()
        w.grab().save(str(output / "operation-voice-settings.png"))
    finally:
        w.cleanup(); shiboken6.delete(w)
(output / "smoke-operation-voices.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report)); sys.exit(0 if all(report.values()) else 1)
