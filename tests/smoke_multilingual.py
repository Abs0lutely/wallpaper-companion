"""Isolated native multilingual controls; never starts a speech API."""
import json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QPushButton,QMessageBox
from companion.core import ROOT,Store,new_profile
from companion.ui import Window
from companion.operation_rules_ui import OperationRulesDialog
from companion.i18n import tr
import shiboken6
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
report={};errors=[]
with tempfile.TemporaryDirectory(dir=ROOT/"output") as tmp,patch("companion.managed_api.api") as api,patch("companion.secrets.read_secret",return_value=""),patch("companion.secrets.write_secret"):
    root=Path(tmp);store=Store(root/"data/config.json")
    profile=new_profile("Native multilingual")
    voice=root/"voice";voice.mkdir();profile["voice_dir"]=str(voice)
    store.config.update(profiles=[profile],manual_profile=profile["id"],operation_voice_enabled=False);store.save()
    w=Window(store,hooks=False);w.report_error=errors.append;w.show()
    try:
        w.poll.stop();w.tick.stop()
        report["single_library_generation_action"]=not any(b.text()=="按分类生成勾选台词" for b in w.findChildren(QPushButton))
        combo=w.provider_widgets["text_lang"];combo.setText("ja")
        w.provider_widgets["prompt_lang"].setText("en")
        report["language_codes_saved"]=w.save_tts() and Store(store.path).config["tts"]["text_lang"]=="ja"
        combo.setEditText("custom-code")
        report["custom_language_preserved"]=w.tts_settings()["text_lang"]=="custom-code"
        w.load_tts();report["language_reload"]=w.provider_widgets["text_lang"].code()=="ja"
        def reject_warning():
            for dialog in app.topLevelWidgets():
                if isinstance(dialog,QMessageBox):
                    for b in dialog.buttons():
                        if b.text()==tr("tts.back","返回修改"):b.click();return
        QTimer.singleShot(30,reject_warning)
        provider=w.registry.speech["gpt_sovits"]
        report["language_warning_can_return_without_api"]=not w.confirm_generation_language(["こんにちは、今日もよろしくね。"],dict(text_lang="zh",prompt_lang="en",prompt="Hello there."),provider)
        report["cross_language_reference_allowed"]=w.confirm_generation_language(["Good morning!"],dict(text_lang="en",prompt_lang="ja",prompt="こんにちは、今日もよろしくね。"),provider)
        d=OperationRulesDialog(w)
        old=d.values();d.locale_choice.setCurrentIndex(d.locale_choice.findData("ja-JP"));d.switch_categories()
        report["operation_bulk_switch"]=all(r["category"].endswith("·ja-JP") for r in d.values()["rules"]) and d.values()["min_interval"]==old["min_interval"]
        report["operation_switch_is_draft"]=store.config["operation_voice_rules"]==old["rules"]
        d.close();shiboken6.delete(d)
        w.select_dialogues("all");w.send_dialogues_to_tts()
        report["transfer_keeps_categories"]=len(w.transferred_dialogues)==38 and w.tts_output.text()==str(voice)
        w.lines.setPlainText("Modified text")
        report["transfer_edit_notice"]=tr("voices.transfer_edited","文本已修改：将按普通逐行模式保存到输出目录，不再使用原分类。")==w.tts_status.text()
        report["no_errors"]=not errors
        api.ensure.assert_not_called();api.start.assert_not_called()
    finally:w.cleanup();shiboken6.delete(w)
(ROOT/"output/smoke-multilingual.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report));assert all(report.values()),report
