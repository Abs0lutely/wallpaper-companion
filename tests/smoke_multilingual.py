"""Isolated native multilingual controls; never starts a speech API."""
import json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QPushButton,QMessageBox
from companion.i18n import set_language,install_qt_translation
locale=globals().get("TEST_LANGUAGE","zh-CN")
set_language(locale)
from companion.core import ROOT,Store,new_profile
from companion.ui import Window
from companion.operation_rules_ui import OperationRulesDialog
from companion.i18n import tr
import shiboken6
app=QApplication([]);app.setQuitOnLastWindowClosed(False);install_qt_translation(app)
report={};errors=[]
with tempfile.TemporaryDirectory(dir=ROOT/"output") as tmp,patch("companion.managed_api.api") as api,patch("companion.secrets.read_secret",return_value=""),patch("companion.secrets.write_secret"):
    root=Path(tmp);store=Store(root/"data/config.json")
    profile=new_profile("Native multilingual")
    voice=root/"voice";voice.mkdir();profile["voice_dir"]=str(voice)
    store.config.update(profiles=[profile],manual_profile=profile["id"],operation_voice_enabled=False);store.save()
    w=Window(store,hooks=False);w.report_error=errors.append;w.show()
    try:
        w.poll.stop();w.tick.stop()
        report["single_library_generation_action"]=not any(b.text()==tr("ui.b8cb3627c40d","按分类生成勾选台词") for b in w.findChildren(QPushButton))
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
        from companion.voice_locales import translated_lines
        legacy=dict(translated_lines("starter","ja-JP")[0]);legacy["id"]="old-import-id";legacy["category"]=legacy["category"].rsplit("·",1)[0]
        custom={**legacy,"id":"custom","category":"Custom category"}
        w.edit_dialogues=[legacy,custom];w.render_dialogues()
        with patch.object(QMessageBox,"exec",return_value=QMessageBox.StandardButton.Yes):w.migrate_dialogue_categories()
        report["legacy_category_preview_migrates_without_touching_custom"]=w.edit_dialogues[0]["category"].endswith("·ja-JP") and w.edit_dialogues[1]==custom and store.profile(profile["id"])["dialogues"]!=w.edit_dialogues
        target=root/"other-dialogues.json"
        target.write_text('[ {"id":"external","text":"External line","category":"External","enabled":true} ]',encoding="utf-8")
        original=target.read_bytes()
        with patch.object(QMessageBox,"exec",return_value=QMessageBox.StandardButton.Yes):
            w.dialogue_file.setText(str(target))
            report["binding_existing_preview_load"]=w.change_dialogue_file() and w.edit_dialogues[0]["text"]=="External line" and target.read_bytes()==original
            w.dialogue_file.setText("")
            report["binding_detach_keeps_content"]=w.change_dialogue_file() and not store.profile(profile["id"])["dialogue_file"] and w.edit_dialogues[0]["text"]=="External line" and target.read_bytes()==original
        with patch.object(QMessageBox,"exec",return_value=QMessageBox.StandardButton.No):
            w.dialogue_file.setText(str(target))
            report["binding_cancel_keeps_old"]=not w.change_dialogue_file() and not w.accepted_dialogue_file
        from companion.file_dialogs import NativeFileDialog
        with patch.object(NativeFileDialog,"getExistingDirectory",return_value="") as pick:
            from companion.file_dialogs import FileDialogs
            FileDialogs.getExistingDirectory(w.voice_dir,"Pick",str(voice))
            report["picker_starts_in_current_directory"]=pick.call_args.args[2]==str(voice)
        from unittest.mock import Mock
        from PySide6.QtTest import QTest
        original_manual=store.config["manual_profile"]
        old_epoch=w.mode_epoch
        w.run_mode.setCurrentIndex(w.run_mode.findData("standalone"))
        query=Mock(return_value=dict(path="",title="No wallpaper",running=False));detector=Mock(return_value=dict(state="no",detail="Mock silent"));scan=Mock(return_value=dict(records=[],warnings=[]))
        w.registry.wallpapers["wallpaper_engine"]=("Mock WE",query)
        w.registry.audio_detectors["builtin"]=("Mock detector",detector)
        w.registry.libraries["wallpaper_engine"]=("Mock scan",scan)
        w.detect(command=True);w.scan_library();w.probe_original_audio();QTest.qWait(650)
        report["standalone_has_no_we_calls"]=not query.called and not detector.called and not scan.called and not w.poll.isActive()
        report["standalone_profile_active"]=w.is_standalone() and w.active_id==profile["id"] and not w.audio.bgm_blocked
        report["standalone_preserves_we_manual_choice"]=store.config["manual_profile"]==original_manual
        report["standalone_hides_binding_controls"]=not w.detect_button.isVisible() and not w.wallpaper_path.isVisible() and not w.navigation[4].isVisible()
        w.detected(dict(path="STALE",title="Stale",running=True),old_epoch)
        report["stale_we_callback_ignored"]=w.current_display_text==tr("mode.standalone","独立声音伴随")
        second=new_profile("Second sound profile");store.config["profiles"].append(second);w.refresh_profiles(second["id"])
        report["standalone_selection_independent"]=w.active_id==second["id"] and store.config["standalone_profile"]==second["id"] and store.config["manual_profile"]==original_manual
        import wave
        clip=root/"standalone.wav"
        with wave.open(str(clip),"wb") as audio:
            audio.setparams((1,2,16000,0,"NONE","not compressed"));audio.writeframes(b"\0\0"*1600)
        with patch("companion.ui.foreground_state",return_value=dict(own=False,desktop=True,fullscreen=False)),patch.object(w.engine,"choose",return_value=(dict(name="Fixture"),clip)) as choose,patch.object(w.audio,"play_voice") as play:
            for event,key in [("mouse_left",""),("key","fixture-id"),("scheduled","")]:w.input_event(event,key)
            report["standalone_mouse_key_time_pipeline"]=choose.call_count==3 and play.call_count==3
        w.tabs.setCurrentIndex(0)
        w.grab().save(str(ROOT/("output/standalone-home-"+locale+".png")))
        w.run_mode.setCurrentIndex(w.run_mode.findData("wallpaper_engine"))
        report["return_to_we_preserves_profile_choice"]=not w.is_standalone() and store.config["manual_profile"]==original_manual and store.config["standalone_profile"]==second["id"]
        report["mode_change_undo"]=w.autosave.undo() and w.is_standalone() and not w.poll.isActive()
        fresh_store=Store(root/"fresh/config.json")
        fresh=Window(fresh_store,hooks=False)
        try:
            report["fresh_no_we_recommends_standalone"]=tr("mode.recommend","未发现 WE 安装目录，推荐选择独立声音伴随；不需要安装 WE。") in fresh.mode_notice.text()
            fresh.run_mode.setCurrentIndex(fresh.run_mode.findData("standalone"))
            report["fresh_standalone_creates_sound_profile"]=fresh.is_standalone() and len(fresh_store.config["profiles"])==1 and fresh.active_id==fresh_store.config["standalone_profile"] and not fresh.poll.isActive()
            report["standalone_persists_without_we_installation"]=Store(fresh_store.path).config["run_mode"]=="standalone" and not fresh_store.config["profiles"][0]["wallpaper"]
        finally:fresh.cleanup();shiboken6.delete(fresh)
        visits=[];selected_files=[]
        def close_picker():
            picker=app.activeModalWidget()
            visits.append(picker.directory().absolutePath());selected_files.append(picker.selectedFiles());picker.reject()
        for name in ("first-picker","second-picker"):
            folder=root/name;folder.mkdir()
            QTimer.singleShot(70,close_picker)
            FileDialogs.getExistingDirectory(w.voice_dir,"Isolated picker",str(folder))
        report["real_picker_ignores_previous_location"]=visits==[str((root/name).resolve()).replace("\\","/") for name in ("first-picker","second-picker")]
        QTimer.singleShot(70,close_picker)
        FileDialogs.getOpenFileName(w.voice_dir,"Isolated open",str(clip),"Audio (*.wav)")
        report["real_open_picker_selects_current_file"]=visits[-1]==str(root).replace("\\","/") and selected_files[-1]==[str(clip).replace("\\","/")]
        output_file=root/"second-picker/new.json"
        QTimer.singleShot(70,close_picker)
        FileDialogs.getSaveFileName(w.voice_dir,"Isolated save",str(output_file),"JSON (*.json)")
        report["real_save_picker_uses_current_parent"]=visits[-1]==str(output_file.parent).replace("\\","/") and selected_files[-1]==[str(output_file).replace("\\","/")] and not output_file.exists()
        report["no_errors"]=not errors
        api.ensure.assert_not_called();api.start.assert_not_called()
    finally:w.cleanup();shiboken6.delete(w)
(ROOT/("output/smoke-multilingual-"+locale+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report));assert all(report.values()),report
