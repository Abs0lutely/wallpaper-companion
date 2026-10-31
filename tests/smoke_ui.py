"""Run with .conda/python.exe tests/smoke_ui.py. Tests only disposable fixtures."""
import io
import json
import math
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication
from companion.core import Store, new_profile, new_rule
from companion.ui import Window, STYLE, RuleDialog

root = Path(__file__).resolve().parents[1]
output = root / "output"
output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
temp = Path(fixture.name)
for directory in ["voice", "bgm"]:
    (temp / directory).mkdir()
    with wave.open(str(temp / directory / "验证音频.wav"), "wb") as wav:
        import struct
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"".join(struct.pack("<h", int(150 * math.sin(i * 2 * math.pi * 440 / 16000))) for i in range(16000 * 3)))
app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
store = Store(temp / "config.json")
p = new_profile("互动与音频验证", r"C:\fixture\scene.pkg")
p.update(voice_dir=str(temp / "voice"), bgm_dir=str(temp / "bgm"), desktop_only=False, original_audio_policy="allow")
p["rules"].extend([new_rule("mouse_left", "点击回应"), new_rule("random", "早安 · 07:00–10:00")])
p["rules"][-1].update(start="07:00", end="10:00", keyword="早安")
store.config["profiles"] = [p]
store.config["manual_profile"] = p["id"]
store.save()
w = Window(store, hooks=False)
w.show()
errors = []
w.audio.message.connect(lambda message: errors.append(message) if "失败" in message else None)
report = {}

def initial():
    report["active_profile"] = w.active_id == p["id"]
    report["bgm_playing"] = w.audio.bgm.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    assert w.grab().save(str(output / "configuration.png"))
    w.preview_voice()
    QTimer.singleShot(700, voice)

def voice():
    report["voice_playing"] = w.audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    report["ducked_bgm"] = abs(w.audio.bgm_output.volume() - .25 * .25) < .005
    w.toggle_pause()
    report["pause_stops_voice"] = not w.audio.busy
    report["pause_stops_bgm"] = w.audio.bgm.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    w.toggle_pause()
    w.tabs.setCurrentIndex(1)
    assert w.grab().save(str(output / "interaction-rules.png"))
    w.tabs.setCurrentIndex(2)
    assert w.grab().save(str(output / "tts.png"))
    w.provider_choice.setCurrentIndex(w.provider_choice.findData("azure_speech"))
    app.processEvents()
    report["azure_dynamic_fields"] = {"url", "api_key", "voice", "locale"}.issubset(w.provider_widgets)
    w.provider_widgets["api_key"].setText("fixture-secret-not-to-disk")
    from unittest.mock import patch
    with patch("companion.secrets.write_secret") as save_secret:
        saved = w.save_tts()
        report["secret_saved_to_os_store"] = saved and save_secret.call_args.args == ("azure_speech", "fixture-secret-not-to-disk")
    report["secret_not_in_json"] = "fixture-secret-not-to-disk" not in store.path.read_text(encoding="utf-8")
    app.processEvents()
    assert w.grab().save(str(output / "azure-provider.png"))
    w.provider_choice.setCurrentIndex(w.provider_choice.findData("gpt_sovits"))
    dialog = RuleDialog(p["rules"][-1], w)
    dialog.show()
    app.processEvents()
    assert dialog.grab().save(str(output / "rule.png"))
    dialog.close()
    w.tabs.setCurrentIndex(0)
    w.profile_name.setText("已保存的测试配置")
    w.save_profile()
    report["saved_from_ui"] = Store(store.path).config["profiles"][0]["name"] == "已保存的测试配置"
    store.config["manual_profile"] = ""
    w.current = dict(path=r"C:\fixture\scene.pkg", title="匹配壁纸", running=True)
    w.activate_profile(force=True)
    report["auto_matching"] = w.active_id == p["id"]
    w.current = dict(path=r"C:\other\scene.pkg", title="其他壁纸", running=True)
    w.activate_profile()
    report["unbound_wallpaper_stops_audio"] = w.active_id is None and w.audio.bgm.source().isEmpty()
    report["media_errors"] = errors
    (output / "smoke-ui.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    w.cleanup()
    app.quit()

QTimer.singleShot(2200, initial)
QTimer.singleShot(12000, lambda: (print("SMOKE_TIMEOUT"), w.cleanup(), app.exit(2)))
code = app.exec()
import shiboken6
shiboken6.delete(w)
app.processEvents()
fixture.cleanup()
if not all(v is True for k, v in report.items() if k != "media_errors") or errors:
    sys.exit(1)
sys.exit(code)
