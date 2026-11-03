"""Reproduce editing an imported voice-only pack; use isolated data and no live API."""
import json,sys,tempfile,wave
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import shiboken6
from companion.core import ROOT,Store,new_profile,new_rule
from companion.packs import plan_export,write_export,PackPreview,install_and_use
from companion.rules_ui import RuleDialog
from companion.ui import Window
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
errors=[]
with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='pack-edit-') as tmp,patch('companion.managed_api.api') as api,patch('companion.secrets.read_secret',return_value=''),patch('companion.secrets.write_secret'):
    root=Path(tmp);voice=root/'source/voice/test';voice.mkdir(parents=True)
    with wave.open(str(voice/'hello.wav'),'wb') as f:
        f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\x01\x01'*1600)
    source=new_profile('Voice only');source.update(voice_dir=str(voice.parent),rules=[dict(new_rule(),source='test')],dialogues=[dict(id='line',category='test',text='hello',enabled=True)])
    archive=write_export(plan_export(source,dict(name='Imported voice pack',language='en-US')),root/'voice.wcpak')
    store=Store(root/'data/config.json');store.config['operation_voice_enabled']=False
    with PackPreview(archive,root/'temp') as preview:identifier,_=install_and_use(store,preview.pack)
    # Recreate the exact old v0.11.0 layout, exclusively inside this disposable fixture.
    old_bgm=Path(store.profile(identifier)['bgm_dir'])
    assert old_bgm.resolve().is_relative_to(root.resolve())
    if old_bgm.is_dir():old_bgm.rmdir()
    w=Window(store,hooks=False);w.poll.stop();w.tick.stop();w.report_error=errors.append;w.show()
    try:
        w.rules_table.selectRow(0)
        def change_rule():
            dialog=app.activeModalWidget();assert isinstance(dialog,RuleDialog)
            dialog.cooldown.setValue(21);dialog.accept()
        QTimer.singleShot(50,change_rule);w.edit_rule()
        saved=w.save_profile()
        print(json.dumps(dict(saved=saved,errors=errors,voice_exists=Path(w.voice_dir.text()).is_dir(),bgm_exists=Path(w.bgm_dir.text()).is_dir()),ensure_ascii=False))
        assert saved, 'Imported pack rule edit could not be saved: '+str(errors)
        assert Store(store.path).profile(identifier)['rules'][0]['cooldown']==21
        # Navigation autosave and undo use the same repaired profile.
        w.tabs.setCurrentIndex(1);w.edit_rules[0]['cooldown']=22;w.render_rules()
        w.tabs.setCurrentIndex(2)
        assert Store(store.path).profile(identifier)['rules'][0]['cooldown']==22
        assert w.autosave.undo()
        assert Store(store.path).profile(identifier)['rules'][0]['cooldown']==21
        # A failed save removes only the empty channel it created and keeps the draft retryable.
        old_bgm.rmdir();w.edit_rules[0]['cooldown']=23
        with patch.object(store,'save',side_effect=OSError('simulated save failure')):
            assert not w.save_profile()
        assert not old_bgm.exists()
        assert Store(store.path).profile(identifier)['rules'][0]['cooldown']==21
        assert w.save_profile()
        assert Store(store.path).profile(identifier)['rules'][0]['cooldown']==23
        # Existing directory validation remains strict for user-entered custom paths.
        custom=root/'missing-custom-voice';old_voice=w.voice_dir.text();w.voice_dir.setText(str(custom))
        assert not w.save_profile() and not custom.exists()
        w.voice_dir.setText(old_voice)
        print('manual-save / navigation-autosave / undo / failed-save rollback / retry / custom-path validation: PASS')
        api.start.assert_not_called();api.ensure.assert_not_called()
    finally:w.cleanup();shiboken6.delete(w)
