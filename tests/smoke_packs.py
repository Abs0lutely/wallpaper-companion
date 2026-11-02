"""Real native browser flows in isolated stores; never calls a real API."""
import copy,json,tempfile,sys,time,wave
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QDialog,QCheckBox,QDialogButtonBox
from PySide6.QtCore import QTimer,QEventLoop
from companion.i18n import set_language,install_qt_translation
locale=globals().get('TEST_LANGUAGE','zh-CN');set_language(locale)
from companion.core import ROOT,Store,new_profile,new_rule
from companion.packs import plan_export,write_export,PackPreview
from companion.packs_ui import PackBrowser
from companion.ui import Window
import shiboken6
app=QApplication([]);app.setQuitOnLastWindowClosed(False);install_qt_translation(app)
report={};errors=[]
def wait(predicate):
    deadline=time.monotonic()+15
    while not predicate() and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert predicate(),'UI job timed out'
def accept():
    d=app.activeModalWidget()
    report['operation_unchecked_by_default']=not d.findChild(QCheckBox).isChecked()
    d.accept()
with tempfile.TemporaryDirectory(dir=ROOT/'output') as tmp,patch('companion.managed_api.api') as api,patch('companion.secrets.read_secret',return_value=''),patch('companion.secrets.write_secret'):
    root=Path(tmp);store=Store(root/'data/config.json');profile=new_profile('Previous profile')
    voice=root/'voice';voice.mkdir();clip=voice/'hello.wav'
    with wave.open(str(clip),'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\x01\x01'*3200)
    profile.update(voice_dir=str(voice),dialogues=[dict(id='hello',category='test',text='hello',enabled=True)],rules=[new_rule()])
    store.config.update(profiles=[profile],run_mode='standalone',standalone_profile=profile['id'],operation_voice_enabled=False);store.save()
    w=Window(store,hooks=False);w.report_error=errors.append;w.show();w.poll.stop();w.tick.stop()
    browser=None
    try:
        archive=write_export(plan_export(profile,dict(name='Native pack',character='Test',language='en-US')),root/'native.wcpak')
        before=copy.deepcopy(store.config);w.toggle_pause()
        browser=PackBrowser(w);browser.show();wait(lambda:not browser.busy)
        with patch('companion.packs_ui.FileDialogs.getOpenFileName',return_value=(str(archive),'')),patch('companion.packs_ui.info_dialog'):
            browser.import_file();wait(lambda:not browser.busy)
        report['import_does_not_change_configuration']=store.config==before
        pack=browser.previews[-1].pack
        with patch.object(browser.audio,'play_voice') as play:
            browser.perform(pack,'preview');report['preview_uses_own_player']=play.call_count==1 and store.config==before
        QTimer.singleShot(50,accept);browser.perform(pack,'use');wait(lambda:not browser.busy)
        new_id=w.editing_id
        report['use_creates_independent_profile']=new_id!=profile['id'] and w.is_standalone() and len(store.config['profiles'])==2
        report['pause_preserved']=w.paused and w.audio.paused and browser.start.isVisible()
        report['original_configuration_preserved']=store.profile(profile['id'])==before['profiles'][0]
        report['operation_settings_preserved']=store.config['operation_voice_rules']==before['operation_voice_rules'] and store.config['operation_voice_enabled']==False
        report['no_fallback']=not store.profile(new_id)['use_bundled_demo'] and not store.profile(new_id)['dialogue_file']
        browser.return_previous();report['return_keeps_new_pack']=w.active_id==profile['id'] and store.profile(new_id) is not None
        browser.start_companion();report['explicit_start']=not w.paused
        browser.resize(640,480);app.processEvents();browser.grab().save(str(ROOT/f'output/packs-{locale}.png'))
        report['no_errors']=not errors
        api.start.assert_not_called();api.ensure.assert_not_called()
    finally:
        if browser:browser.reject();shiboken6.delete(browser)
        w.cleanup();shiboken6.delete(w)
(ROOT/f'output/smoke-packs-{locale}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report));assert all(report.values()),report
