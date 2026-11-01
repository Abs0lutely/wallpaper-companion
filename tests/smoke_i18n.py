"""Native language settings and data compatibility with isolated data and mocked APIs."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import wave
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.i18n import set_language, language, install_qt_translation, tr
locale = globals().get("TEST_LANGUAGE", "en-US")
set_language(locale)
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QMessageBox, QDialogButtonBox
from companion.core import ROOT, Store, new_profile, new_rule
from companion.ui import Window, STYLE
from companion.rules_ui import RuleDialog
from companion.resources_ui import ResourceDialog
from companion.operation_rules_ui import OperationRulesDialog
from companion.library_ui import DialogueDialog
from companion.presets_ui import PresetImportDialog
from companion.presets import export_payload
from companion.operation_voices import classify_button
from companion.services import generate
import shiboken6

app=QApplication([]); app.setQuitOnLastWindowClosed(False); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
install_qt_translation(app)
report={}; errors=[]; dialogs=[]
with tempfile.TemporaryDirectory(dir=ROOT/'output') as tmp, patch('companion.managed_api.api') as api, patch('companion.secrets.read_secret',return_value=''), patch('companion.secrets.write_secret'):
    root=Path(tmp)
    store=Store(root/'data/config.json')
    p=new_profile('用户配置：测试角色',str(root/'wallpaper.pkg'))
    (root/'wallpaper.pkg').write_bytes(b'fixture')
    for key,name in [('voice_dir','voice'),('bgm_dir','bgm')]:
        (root/name).mkdir(); p[key]=str(root/name)
    p.update(desktop_only=False,fullscreen_mute=False,original_audio_policy='allow')
    store.config.update(ui_language=locale,profiles=[p],manual_profile=p['id'],shared_asset_dir=str(root/'shared'))
    store.save(); saved_content=copy.deepcopy(p['dialogues'])
    w=Window(store,hooks=False); w.show(); w.report_error=errors.append
    try:
        w.poll.stop()
        report['localized_navigation']=w.navigation[0].text().endswith('Companion home' if locale=='en-US' else '陪伴主页')
        report['localized_provider_and_hover']=w.provider_choice.itemText(0)==('Local GPT-SoVITS' if locale=='en-US' else '本地 GPT-SoVITS') and ('reference' in w.character_choice.toolTip().lower() if locale=='en-US' else '角色' in w.character_choice.toolTip())
        report['user_content_kept']=w.profile_name.text()==p['name'] and w.edit_dialogues==saved_content
        report['no_generation_selected']=not w.selected_dialogues()
        english_titles={3:'Runtime settings',4:'Wallpaper library',5:'Dialogue library',6:'Audio library'}
        report['all_tab_captions']=all(w.tabs.tabText(i)==t for i,t in english_titles.items()) if locale=='en-US' else w.tabs.tabText(3)=='运行设置'
        for index in (0,4,6,5,2,3):
            w.tabs.setCurrentIndex(index); QTest.qWait(80)
            report['page_'+str(index)]=w.tabs.currentIndex()==index
            w.grab().save(str(ROOT/'output'/('i18n-'+locale+'-'+str(index)+'.png')))
        other='zh-CN' if locale=='en-US' else 'en-US'
        w.ui_language.setCurrentIndex(w.ui_language.findData(other))
        report['pending_notice']=bool(w.language_notice.text()) and language()==locale
        report['manual_save']=w.save_settings() and Store(store.path).config['ui_language']==other and language()==locale
        w.ui_language.setCurrentIndex(w.ui_language.findData(locale)); w.save_settings()
        w.ui_language.setCurrentIndex(w.ui_language.findData(other)); w.tabs.setCurrentIndex(0)
        report['navigation_autosave']=Store(store.path).config['ui_language']==other and w.autosave.undo_button.isEnabled()
        report['autosave_restart_notice']=tr('settings.language_next_start','界面语言将在下次启动时生效。') in w.autosave.label.text()
        report['undo_language']=w.autosave.undo() and Store(store.path).config['ui_language']==locale and w.ui_language.currentData()==locale
        w.tabs.setCurrentIndex(3); w.ui_language.setCurrentIndex(w.ui_language.findData(other))
        old=store.path.read_bytes()
        with patch.object(store,'save',side_effect=OSError('simulated save failure')):
            report['save_failure_keeps_language']=not w.save_settings() and store.path.read_bytes()==old and store.config['ui_language']==locale
        errors.clear(); w.load_settings()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):w.restore_defaults()
        report['restore_defaults_keeps_content']=Store(store.path).config['ui_language']=='zh-CN' and Store(store.path).profile(p['id'])['dialogues']==saved_content and language()==locale
        report['restore_undo']=w.autosave.undo() and Store(store.path).config['ui_language']==locale
        # Exercise both actual help buttons, including reopen and local navigation.
        from PySide6.QtGui import QImage, QColor
        background=QImage(16,16,QImage.Format.Format_RGB32);background.fill(QColor('#ff0055'))
        image_path=root/'test-parent-background.png';background.save(str(image_path))
        w.setStyleSheet('QWidget {background-image:url("'+image_path.as_posix()+'");}')
        guide_button=next(b for b in w.findChildren(QPushButton) if b.text()==('Open user guide' if locale=='en-US' else '打开使用手册'))
        guide_button.click();QTest.qWait(50)
        viewer=w.document_viewer
        expected='USER_GUIDE.en.md' if locale=='en-US' else 'USER_GUIDE.md'
        report['localized_manual_button']=viewer.isVisible() and viewer.current_path.name==expected and ('Features and fields' in viewer.browser.toPlainText() if locale=='en-US' else '功能和输入框' in viewer.browser.toPlainText())
        report['opaque_document_background']=viewer.browser.viewport().grab().toImage().pixelColor(3,3).name()=='#fffdf9'
        viewer.resize(700,540);QTest.qWait(30)
        report['manual_reflows']=viewer.browser.horizontalScrollBar().maximum()==0
        report['manual_opens_at_top']=viewer.browser.verticalScrollBar().value()==0
        viewer.grab().save(str(ROOT/'output'/('help-'+locale+'-manual.png')))
        from PySide6.QtCore import QUrl
        viewer.follow_link(QUrl('USAGE.md'))
        report['localized_document_links']=viewer.current_path.name==('USAGE.en.md' if locale=='en-US' else 'USAGE.md')
        viewer.close();w.tabs.setCurrentIndex(3)
        overview_button=next(b for b in w.findChildren(QPushButton) if b.text()==('Open documentation' if locale=='en-US' else '打开使用说明'))
        overview_button.click();QTest.qWait(50)
        text=viewer.browser.toPlainText()
        report['localized_overview_button']=viewer.isVisible() and ('Hear your first response' in text if locale=='en-US' else '先听到第一句回应' in text)
        block=viewer.browser.document().begin(); has_image=False
        while block.isValid():
            fragment=block.begin()
            while not fragment.atEnd():
                if fragment.fragment().charFormat().isImageFormat(): has_image=True
                fragment+=1
            block=block.next()
        report['no_promotional_images']=not has_image and '<img' not in text and '[![' not in text
        from PySide6.QtGui import QTextDocument
        report['remote_images_disabled']=viewer.browser.loadResource(QTextDocument.ResourceType.ImageResource,QUrl('https://example.invalid/banner.png')).isNull()
        viewer.grab().save(str(ROOT/'output'/('help-'+locale+'-overview.png')))
        with patch.object(QMessageBox,'warning') as warning:
            old=viewer.current_path
            viewer.follow_link(QUrl('missing-manual.md'))
            report['failed_help_navigation_keeps_page']=warning.called and viewer.current_path==old
        viewer.close();w.setStyleSheet('')
        w.tabs.setCurrentIndex(1)
        r=RuleDialog(new_rule(),w)
        dialogs.append(r)
        report['localized_rule_dialog']='choose trigger' in r.windowTitle() if locale=='en-US' else '选择触发方式' in r.windowTitle()
        r.hotkey.setText('F8'); r._binding='<f8>'; r.accept()
        report['rule_ids_preserved']=r.rule['event']=='key' and r.rule['hotkey']=='<f8>'
        resource=ResourceDialog(store,p,w); dialogs.append(resource)
        report['directory_mode_ids']=resource.modes['voice_dir'].itemData(0)=='shared'
        operation=OperationRulesDialog(w); dialogs.append(operation)
        report['operation_categories_unchanged']=operation.values()['rules']==store.config['operation_voice_rules']
        report['operation_action_english']=operation.table.item(0,1).text()=='Response' if locale=='en-US' else operation.table.item(0,1).text()=='回应'
        dialogue=DialogueDialog(saved_content[0],w); dialogs.append(dialogue)
        report['dialogue_editor_keeps_category']=dialogue.category.currentText()==saved_content[0]['category']
        preset=PresetImportDialog([p],[],p,w);dialogs.append(preset)
        report['preset_internal_mode']=preset.mode.itemData(0)=='new' and preset.mode.itemData(1)=='replace'
        for dialog in dialogs:
            dialog.show();QTest.qWait(30)
            dialog.grab().save(str(ROOT/'output'/('i18n-'+locale+'-'+type(dialog).__name__+'.png')))
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        report['qt_standard_buttons']=controls.button(QDialogButtonBox.StandardButton.Cancel).text().replace('&','')==('Cancel' if locale=='en-US' else '取消')
        pairs={'保存接口设置':'save','关闭自建 API':'api_stop','启动本地 API':'api_start','播放参考音频':'preview','下一首 BGM':'next','删除':'delete'}
        from companion.translations_en import SOURCES
        for source,event in pairs.items():
            key=next(k for k,v in SOURCES.items() if v==source)
            report['voice_event_'+event]=classify_button(QPushButton(tr(key,source)))==event
        # Exercise the real generation buttons/progress with an in-process fake provider.
        from companion.extensions import SpeechProvider
        wav=io.BytesIO()
        with wave.open(wav,'wb') as audio:
            audio.setparams((1,2,16000,0,'NONE','not compressed'))
            audio.writeframes(b'\x00\x00'*1600)
        generated=[]
        def synthesize(settings,text):
            generated.append(text)
            return wav.getvalue()
        w.registry.register_speech(SpeechProvider('mock','Mock provider',[],synthesize,lambda settings:'Ready'))
        w.provider_choice.addItem('Mock provider','mock')
        w.provider_choice.setCurrentIndex(w.provider_choice.findData('mock'))
        w.tabs.setCurrentIndex(2)
        w.lines.setPlainText('仅用于隔离测试的台词')
        w.filename_model.setText('测试模型')
        w.tts_output.setText(str(root/'generated'))
        w.generate_button.click()
        deadline=time.monotonic()+8
        while w.tts_busy and time.monotonic()<deadline: QTest.qWait(50)
        report['mock_generation_flow']=not w.tts_busy and generated==['仅用于隔离测试的台词'] and (root/'generated/仅用于隔离测试的台词-测试模型.wav').exists()
        report['localized_generation_progress']=('Saved 1' in w.tts_status.text() if locale=='en-US' else '已保存 1' in w.tts_status.text()) and w.tts_progress.value()==1
        w.tabs.setCurrentIndex(0); w.resize(1024,768); QTest.qWait(50)
        report['compact_window_fits']=w.width()<=1024 and w.height()<=768
        w.grab().save(str(ROOT/'output'/('i18n-'+locale+'-compact.png')))
        api.ensure.assert_not_called(); api.start.assert_not_called()
        report['no_api_started']=True
        report['no_ui_errors']=not errors
    finally:
        for dialog in dialogs: dialog.hide();shiboken6.delete(dialog)
        w.cleanup(); shiboken6.delete(w)
result={'locale':locale,'device_pixel_ratio':app.primaryScreen().devicePixelRatio(),'checks':report,'errors':errors}
(ROOT/'output'/('i18n-'+locale+'-report.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
assert all(report.values()),report
