"""Visible action acknowledgements and honest generation progress with fake TTS."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import wave
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QPushButton, QVBoxLayout
from companion.core import ROOT, Store
from companion.ui import Window, STYLE
import shiboken6

output = ROOT/"output"; output.mkdir(exist_ok=True)
fixture = tempfile.TemporaryDirectory(dir=output); root = Path(fixture.name)
stream = io.BytesIO()
with wave.open(stream,"wb") as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b"\x01\x00"*160)
store = Store(root/"data/config.json"); store.config.update(we_dir="", workshop_dir="")
app=QApplication([]); app.setQuitOnLastWindowClosed(False); app.setStyle("Fusion"); app.setStyleSheet(STYLE)
report, errors = {}, []
def wait(predicate):
    end=time.monotonic()+6
    while not predicate():
        assert time.monotonic()<end, "generation feedback timeout"
        QTest.qWait(20)
with patch("companion.managed_api.api") as api, patch("companion.secrets.read_secret",return_value=""),patch("companion.secrets.write_secret"):
    api.owns_service.return_value=False
    w=Window(store,hooks=False); w.show(); w.navigation[2].click(); w.report_error=errors.append
    w.filename_model.setText("测试模型")
    def synthesize(settings,text):
        for stage in ("等待模型加载（模拟）", "正在合成（模拟）"):
            settings["_tts_status"](stage); time.sleep(.07)
        if text == "失败条目": raise ValueError("fixture generation failed")
        return stream.getvalue()
    api.synthesize.side_effect=synthesize
    try:
        button=QPushButton("动态测试动作",w); button.show(); QTest.qWait(40); button.click()
        report["dynamic_button_has_visible_acknowledgement"]="动态测试动作" in w.action_feedback.label.toolTip() and w.action_feedback.toast.isVisible()
        dialog=QDialog(w); layout=QVBoxLayout(dialog); box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok,dialog); layout.addWidget(box); dialog.show(); QTest.qWait(40)
        box.button(QDialogButtonBox.StandardButton.Ok).click()
        title=box.button(QDialogButtonBox.StandardButton.Ok).text().replace("&", "")
        report["dialog_button_has_feedback"]=bool(title) and title in w.action_feedback.label.toolTip()
        if not report["dialog_button_has_feedback"]: print("Dialog feedback:",title,w.action_feedback.label.toolTip(),flush=True)
        dialog.close(); shiboken6.delete(dialog)
        w.tts_output.setText(str(root/"success")); w.lines.setPlainText("第一条测试\n第二条测试"); w.generate_audio()
        report["progress_starts_at_zero_with_activity"]=w.tts_progress.value()==0 and not w.tts_activity.isHidden()
        wait(lambda:not w.tts_busy)
        report["success_progress_reflects_saved_items"]=w.tts_progress.value()==2 and w.tts_progress.maximum()==2 and w.tts_activity.isHidden()
        report["stage_output_includes_api_and_saving"]="等待模型" in w.tts_stage_output.toPlainText() and "WAV" in w.tts_stage_output.toPlainText()
        w.tts_output.setText(str(root/"failed")); w.lines.setPlainText("保留第一条\n失败条目"); w.generate_audio(); wait(lambda:not w.tts_busy)
        report["failure_does_not_falsely_reach_completion"]=w.tts_progress.value()==1 and w.tts_progress.maximum()==2 and w.tts_activity.isHidden() and "未完成" in w.tts_progress.format()
        report["failure_keeps_saved_file_and_reports_error"]=(root/"failed/保留第一条-测试模型.wav").is_file() and len(errors)==1 and "fixture generation failed" in errors[0]
        w.hide(); QTest.qWait(30)
        report["hiding_window_hides_toast"]=not w.action_feedback.toast.isVisible()
        (output/"smoke-generation-feedback.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report),flush=True)
    finally:
        w.cleanup(); shiboken6.delete(w)
fixture.cleanup()
sys.exit(0 if all(report.values()) else 1)
