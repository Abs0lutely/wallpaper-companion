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
        with patch('companion.bundled_audio.bundled_root',return_value=ROOT/'examples/audio'):
            browser=PackBrowser(w);browser.show();wait(lambda:not browser.busy)
        app.processEvents();browser.grab().save(str(ROOT/f'output/included-packs-{locale}.png'))
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
        from companion.pack_export_ui import PackExportDialog
        export=PackExportDialog(w,store.profile(profile['id']));export.show()
        try:
            report['export_optional_resources_off']=not export.bgm.isChecked() and not export.operation.isChecked() and not export.rights.isChecked()
            music=root/'music';music.mkdir();(music/'song.wav').write_bytes(clip.read_bytes());export.profile['bgm_dir']=str(music);export.bgm.setChecked(True)
            export.preview_resources();wait(lambda:not export.busy)
            report['export_sources_reviewed']=export.files.rowCount()==2 and export.plan is not None and any(str(clip) in export.files.item(row,1).text() for row in range(export.files.rowCount()))
            report['resource_tooltips_keep_full_path']=any(str(clip)==export.files.item(row,1).toolTip() for row in range(export.files.rowCount()))
            export.select_all(False);report['export_deselect_supported']=not export.selected()
            export.select_all(True);export.rights.setChecked(True)
            shared=root/'share.wcpak'
            with patch('companion.pack_export_ui.FileDialogs.getSaveFileName',return_value=(str(shared),'')):
                export.export_file();wait(lambda:not export.busy)
            report['export_written']=shared.exists() and export.open_button.isEnabled()
            from companion.packs import install_and_use
            second_store=Store(root/'second/config.json')
            with PackPreview(shared,root/'second/temp') as imported:
                identifier,_=install_and_use(second_store,imported.pack)
                from companion.core import candidates
                second=second_store.profile(identifier)
                from companion.audio import Audio
                player=Audio();states=[];player.bgm.playbackStateChanged.connect(lambda state:states.append(state));player.set_profile(second)
                from PySide6.QtMultimedia import QMediaPlayer
                wait(lambda:QMediaPlayer.PlaybackState.PlayingState in states)
                report['shared_bgm_actual_qt_playback']=bool(states);player.stop();shiboken6.delete(player)
                report['export_to_fresh_store']=second_store.config['run_mode']=='standalone' and len(candidates(second,second['rules'][0]))==1
            export.fields['name'].setText('Changed name')
            report['export_metadata_change_requires_preview']=export.plan is None
            export.resize(680,520);app.processEvents();export.grab().save(str(ROOT/f'output/pack-export-{locale}.png'))
        finally:export.reject();shiboken6.delete(export)
        from companion.pack_builtins import builtin_catalog,prepare_builtin
        from companion.packs import install_and_use
        from companion.core import RuleEngine,candidates
        from datetime import datetime
        factory_counts=[]
        with patch('companion.bundled_audio.bundled_root',return_value=ROOT/'examples/audio'):
            for entry in builtin_catalog():
                included=prepare_builtin(entry['id'],root/'included-temp')
                try:
                    ready=included.pack
                    factory_counts.append((ready.recordings,len([f for f in ready.manifest['files'] if f['path'].startswith('operation-voice/')]),ready.complete))
                    fresh_store=Store(root/entry['id']/'config.json')
                    new,_=install_and_use(fresh_store,ready,True);fresh=fresh_store.profile(new)
                    engine=RuleEngine()
                    key=next(r for r in fresh['rules'] if r['event']=='key')
                    report['builtin_key_'+entry['language']]=engine.choose(fresh,'key',now=100,clock=datetime(2026,11,2,12),hotkey=key['id']) is not None
                    scheduled=next(r for r in fresh['rules'] if r['event']=='scheduled')
                    report['builtin_scheduled_'+entry['language']]=RuleEngine().choose(fresh,'scheduled',now=100,clock=datetime(2026,11,2,22,30)) is not None
                    # Real Qt decoding/playback uses only the approved included clip.
                    from PySide6.QtMultimedia import QMediaPlayer
                    states=[]
                    browser.audio.voice.playbackStateChanged.connect(lambda state:states.append(state))
                    browser.audio.play_voice(ready.root/ready.manifest['preview'])
                    wait(lambda:QMediaPlayer.PlaybackState.PlayingState in states)
                    browser.audio.stop()
                    report['builtin_actual_qt_playback_'+entry['language']]=QMediaPlayer.PlaybackState.PlayingState in states
                finally:included.close()
            report['included_inventory']=factory_counts==[(38,52,True),(38,52,True)]
            entry=builtin_catalog()[0]
            browser.resolve('builtin',entry,'preview');wait(lambda:not browser.busy)
            browser.audio.stop()
            QTimer.singleShot(50,accept);browser.resolve('builtin',entry,'use');wait(lambda:not browser.busy)
            selected=store.profile(w.active_id)
            report['builtin_through_native_use']=selected is not None and selected.get('pack_install') and not w.paused
            w.audio.stop();w.engine.reset()
            key=next(r for r in selected['rules'] if r['event']=='key')
            states=[];w.audio.voice.playbackStateChanged.connect(lambda state:states.append(state))
            with patch('companion.ui.foreground_state',return_value=dict(own=False,desktop=True,fullscreen=False)):
                w.input_event('key',key['id'])
                wait(lambda:QMediaPlayer.PlaybackState.PlayingState in states)
            report['native_key_to_real_player']=True;w.audio.stop()

        with patch.object(w.autosave,'flush',return_value=False),patch('companion.packs_ui.FileDialogs.getOpenFileName') as picker:
            browser.import_file();report['save_failure_blocks_import']=not picker.called
        # Explicit link action uses a mocked read-only query, never a real WE process.
        from PySide6.QtWidgets import QMessageBox
        fake_wall=str(root/'mock-wallpaper.mp4');backend=store.config.get('wallpaper_backend','wallpaper_engine')
        queries=[]
        def fake_query(config):
            queries.append(config)
            return dict(path=fake_wall,title='Mock wallpaper',running=True)
        original_backend=w.registry.wallpapers[backend]
        w.registry.wallpapers[backend]=('Mock WE',fake_query)
        conflict=new_profile('Existing linked profile',fake_wall);store.config['profiles'].append(conflict);store.save()
        config_before=copy.deepcopy(store.config);browser.link_wallpaper();wait(lambda:not browser.busy)
        report['wallpaper_link_refuses_overwrite']=store.config==config_before
        store.config['profiles'].remove(conflict);store.save()
        with patch('companion.packs_ui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes):
            browser.link_wallpaper();wait(lambda:not browser.busy)
        report['explicit_wallpaper_link']=store.profile(browser.applied_id)['wallpaper']==fake_wall and store.config['run_mode']=='wallpaper_engine'
        report['wallpaper_link_query_read_only']=bool(queries) and all(not q.get('_wallpaper_command_query') for q in queries)
        browser.return_previous();w.poll.stop();app.processEvents()
        w.registry.wallpapers[backend]=original_backend
        text_archive=write_export(plan_export(profile,dict(name='Text only',character='Test',language='en-US')),root/'text.wcpak',[])
        with PackPreview(text_archive,root/'text-temp') as text_only:
            before=copy.deepcopy(store.config);browser.perform(text_only.pack,'preview')
            from companion.pack_text import p
            report['text_only_preview_explains_without_changes']=browser.status.text()==p('no_audio') and store.config==before
        long_entry=copy.deepcopy(builtin_catalog()[0]);long_entry['name']='LongCompanionName'*10;long_entry['description']='LongDescription'*60
        browser.add_card('builtin',long_entry);browser.resize(640,480);app.processEvents();app.processEvents()
        report['long_names_fit_compact_browser']=browser.width()<=650 and browser.content.width()<=browser.scroll.viewport().width()+2
        report['source_services_untouched']=api.ensure.call_count==0 and api.start.call_count==0
        report['no_errors']=not errors
        api.start.assert_not_called();api.ensure.assert_not_called()
    finally:
        if browser:browser.reject();shiboken6.delete(browser)
        w.cleanup();shiboken6.delete(w)
(ROOT/f'output/smoke-packs-{locale}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report));assert all(report.values()),report
