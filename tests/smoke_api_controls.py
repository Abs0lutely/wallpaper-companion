"""Native API controls with a fake backend; never touch a real local service."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from companion.core import ROOT, Store
from companion.assets import shared_root
from companion.ui import Window, STYLE
import shiboken6

output = ROOT / "output"; output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output)
store = Store(Path(fixture.name) / "data/config.json")
store.config.update(we_dir="", workshop_dir="")
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
app.setStyle("Fusion"); app.setStyleSheet(STYLE)
report, errors = {}, []

def wait(predicate):
    deadline = time.monotonic() + 5
    while not predicate():
        assert time.monotonic() < deadline, "UI task timed out"
        QTest.qWait(20)

with patch("companion.managed_api.api") as api, patch("companion.secrets.read_secret", return_value=""), patch("companion.secrets.write_secret"):
    state = dict(owned=False)
    api.owns_service.side_effect = lambda: state["owned"]
    def start(*_):
        time.sleep(.05); state["owned"] = True
        return "自建 API 已就绪"
    def close():
        state["owned"] = False
        return "自建 API 已关闭"
    api.start.side_effect = start; api.close_owned.side_effect = close
    w = Window(store, hooks=False); w.show(); w.navigation[2].click()
    w.report_error = errors.append
    try:
        report["local_api_button_visible"] = w.start_api_button.isVisible() and w.start_api_button.text() == "启动本地 API"
        next(b for b in w.findChildren(QPushButton) if b.text() == "保存接口设置").click()
        report["save_has_visible_feedback"] = "已保存" in w.tts_status.text() and store.path.exists()
        w.use_voice_dir()
        report["directory_button_has_feedback_and_shared_fallback"] = w.tts_output.text() == str(shared_root(store) / "voice") and "目录已切换" in w.tts_status.text()
        provider = w.registry.speech["gpt_sovits"]
        def disconnected(_): raise requests.ConnectionError("HTTPConnectionPool fixture refused")
        provider.check = disconnected
        w.check_api_button.click(); wait(lambda: not w.api_busy)
        report["cold_check_is_actionable_without_start"] = "尚未启动" in w.tts_status.text() and "HTTPConnectionPool" not in w.tts_status.text() and not api.start.called
        w.start_api_button.click()
        report["startup_disables_conflicting_actions"] = w.api_busy and not w.generate_button.isEnabled() and not w.check_api_button.isEnabled()
        wait(lambda: not w.api_busy)
        report["start_switches_to_close"] = w.start_api_button.text() == "关闭自建 API" and "就绪" in w.tts_status.text()
        w.tts_busy = True; w.update_api_controls(); w.launch_api()
        report["generation_prevents_manual_shutdown"] = not api.close_owned.called and not w.start_api_button.isEnabled()
        w.tts_busy = False; w.update_api_controls()
        w.start_api_button.click(); wait(lambda: not w.api_busy)
        report["close_resets_start_action"] = not state["owned"] and w.start_api_button.text() == "启动本地 API" and "已关闭" in w.tts_status.text()
        api.start.side_effect = lambda *_: "已连接外部 API；不会关闭外部服务"
        w.start_api_button.click(); wait(lambda: not w.api_busy)
        report["external_service_never_gets_close_action"] = w.start_api_button.text() == "启动本地 API" and "外部" in w.tts_status.text() and api.close_owned.call_count == 1
        api.start.side_effect = ValueError("fixture startup failure")
        w.start_api_button.click(); wait(lambda: not w.api_busy)
        report["startup_error_restores_controls"] = w.start_api_button.isEnabled() and w.generate_button.isEnabled() and "fixture startup failure" in w.tts_status.text()
        report["no_synthesis_or_ui_errors"] = not api.synthesize.called and not errors
        (output / "smoke-api-controls.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    finally:
        w.cleanup(); shiboken6.delete(w)
fixture.cleanup()
sys.exit(0 if all(report.values()) else 1)
