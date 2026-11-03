import copy,json,tempfile,unittest,wave,zipfile,hashlib,stat
from pathlib import Path
from unittest.mock import patch
from companion.core import Store,new_profile,new_rule,candidates
from companion.packs import *
from companion.operation_rules import config_payload

ROOT=Path(__file__).resolve().parents[1]
TEMP=ROOT/'output'/'pack-unit';TEMP.mkdir(parents=True,exist_ok=True)

def wav(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\x01\x01'*1600)

class PackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=TEMP);self.root=Path(self.tmp.name)
        self.store=Store(self.root/'a/config.json');self.profile=new_profile('original')
        self.voice=self.root/'source/voice';wav(self.voice/'test/hello-model.wav')
        self.profile.update(voice_dir=str(self.voice),use_bundled_demo=False,dialogues=[dict(id='line',text='hello',category='test',enabled=True)],rules=[dict(new_rule(),source='test')])
        self.store.config['profiles']=[self.profile];self.store.save()
        self.before=self.store.path.read_bytes();self.audio=digest(self.voice/'test/hello-model.wav')
    def tearDown(self):self.tmp.cleanup()
    def plan(self,**kw):return plan_export(self.profile,dict(name='My pack',character='Actor',language='en-US'),**kw)
    def archive(self):return write_export(self.plan(),self.root/'test.wcpak')
    def test_round_trip_preview_install_repeat_and_return(self):
        archive=self.archive()
        with PackPreview(archive,self.root/'temp') as preview:
            pack=preview.pack;self.assertTrue(pack.complete)
            self.assertEqual(self.store.path.read_bytes(),self.before)
            old=copy.deepcopy(self.store.config)
            new,previous=install_and_use(self.store,pack)
            self.assertEqual(previous,old);self.assertEqual(len(self.store.config['profiles']),2)
            self.assertFalse(self.store.profile(new)['use_bundled_demo'])
            self.assertEqual(len(candidates(self.store.profile(new),self.store.profile(new)['rules'][0])),1)
            second,_=install_and_use(self.store,pack)
            self.assertNotEqual(new,second);self.assertEqual(len(list((self.root/'a/packs').iterdir())),1)
            restore_selection(self.store,previous);self.assertEqual(len(self.store.config['profiles']),3)
            self.assertEqual(self.store.config['manual_profile'],old['manual_profile'])
        self.assertEqual(digest(self.voice/'test/hello-model.wav'),self.audio)
    def test_failure_rollback_and_preserve_existing_installs(self):
        with PackPreview(self.archive(),self.root/'tmp') as preview:
            with patch.object(self.store,'save',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):install_and_use(self.store,preview.pack)
            self.assertEqual(self.store.path.read_bytes(),self.before);self.assertEqual(len(self.store.config['profiles']),1)
            self.assertEqual(list((self.root/'a/packs').iterdir()),[])
            install_and_use(self.store,preview.pack);before=copy.deepcopy(self.store.config)
            with patch.object(self.store,'save',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):install_and_use(self.store,preview.pack)
            self.assertEqual(self.store.config,before);self.assertEqual(len(list((self.root/'a/packs').iterdir())),1)
    def test_export_never_leaks_settings_and_respects_exclusion(self):
        self.profile.update(tts=dict(key='secret'),wallpaper='C:/secret/wall.mp4',dialogue_file='')
        archive=write_export(self.plan(),self.root/'empty.wcpak',[])
        with PackPreview(archive,self.root/'tmp') as preview:
            self.assertFalse(preview.pack.complete);self.assertEqual(preview.pack.recordings,0)
            text=(preview.pack.root/'preset.json').read_text(encoding='utf-8')
            self.assertNotIn('secret',text);self.assertNotIn(str(self.voice),text)
            self.assertEqual(len(preview.pack.profile['rules']),1)
            self.assertTrue(preview.pack.manifest['missing_sources'])
    def test_external_file_and_bgm(self):
        file=self.root/'external.wav';wav(file)
        self.profile['rules'][0]['source']=str(file)
        bgm=self.root/'music';wav(bgm/'song.wav');self.profile['bgm_dir']=str(bgm)
        archive=write_export(self.plan(include_bgm=True),self.root/'external.wcpak')
        with PackPreview(archive,self.root/'tmp') as preview:
            rule=preview.pack.profile['rules'][0]
            self.assertFalse(Path(rule['source']).is_absolute())
            self.assertTrue((preview.pack.root/'voice'/rule['source']).is_file())
            self.assertTrue((preview.pack.root/'bgm/song.wav').is_file())
    def test_operation_changes_only_after_explicit_opt_in(self):
        from companion.action_lines import EVENT_LINES
        category=next(iter(EVENT_LINES.values()))[0];wav(self.root/'op'/category/'record.wav')
        operation=config_payload(self.store.config)
        plan=self.plan(operation=operation,operation_roots=[self.root/'op'])
        with PackPreview(write_export(plan,self.root/'op.wcpak'),self.root/'tmp') as preview:
            before=config_payload(self.store.config)
            install_and_use(self.store,preview.pack)
            self.assertEqual(config_payload(self.store.config),before)
            install_and_use(self.store,preview.pack,True)
            self.assertTrue(self.store.config['operation_voice_pack_only'])
    def test_corrupt_source_and_changed_source(self):
        plan=self.plan();(self.voice/'test/hello-model.wav').write_bytes(b'MZexecutable')
        with self.assertRaises(ValueError):write_export(plan,self.root/'bad.wcpak')
        with self.assertRaises(ValueError):write_export(self.plan(),self.root/'bad.wcpak')
        self.assertFalse((self.root/'bad.wcpak').exists())
    def test_unsafe_paths(self):
        for name in ['../x.wav','/x','C:/x','voice/CON.wav','voice/x.','voice/a:b','voice\\x.wav','voice//x','voice/../x','voice/NUL/a']:
            with self.subTest(name=name),self.assertRaises(ValueError):safe_name(name)
    def test_archive_attacks(self):
        original=self.archive()
        with zipfile.ZipFile(original) as z:parts={n:z.read(n) for n in z.namelist()}
        def attack(modifier):
            payload=copy.deepcopy(parts);modifier(payload)
            path=self.root/'attack.wcpak'
            with zipfile.ZipFile(path,'w') as z:
                for name,data in payload.items():z.writestr(name,data)
            with self.assertRaises((ValueError,KeyError,zipfile.BadZipFile)):PackPreview(path,self.root/'tmp')
            self.assertEqual(list((self.root/'tmp').iterdir()),[])
            self.assertEqual(self.store.path.read_bytes(),self.before)
        attack(lambda x:x.update({'../evil.exe':b'MZ'}))
        attack(lambda x:x.update({'voice/x.wav':b'extra'}))
        attack(lambda x:x.update({'PRESET.JSON':x['preset.json']}))
        attack(lambda x:x.update({'preset.json':b'{}'}))
        def oversized(x):
            m=json.loads(x['pack.json']);m['files'][0]['size']=MAX_FILE+1;x['pack.json']=json_bytes(m)
        attack(oversized)
    def test_symlink_zip_rejected(self):
        path=self.root/'link.wcpak'
        with zipfile.ZipFile(path,'w') as z:
            item=zipfile.ZipInfo('voice/link.wav');item.create_system=3;item.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(item,'outside')
        with self.assertRaises(ValueError):PackPreview(path,self.root/'tmp')
    def test_same_name_different_content_kept(self):
        archive=self.archive()
        with PackPreview(archive,self.root/'tmp') as v:install_and_use(self.store,v.pack)
        self.profile['name']='changed'
        with PackPreview(self.archive(),self.root/'tmp') as v:install_and_use(self.store,v.pack)
        self.assertEqual(len(list((self.root/'a/packs').iterdir())),2)

    def test_json_limits_and_duplicate_keys(self):
        archive=self.archive()
        for content in (b'{"files":[],"files":[]}', b'[]', b'{"files":0}'):
            with zipfile.ZipFile(archive,'w') as z:z.writestr('pack.json',content)
            with self.assertRaises((ValueError,KeyError,TypeError)):PackPreview(archive,self.root/'tmp')
            self.assertEqual(list((self.root/'tmp').iterdir()),[])
        archive=self.archive()
        with patch('companion.packs.MAX_JSON',10),self.assertRaises(ValueError):PackPreview(archive,self.root/'tmp')
        with patch('companion.packs.MAX_ARCHIVE',10),self.assertRaises(ValueError):PackPreview(archive,self.root/'tmp')
        with patch('companion.packs.MAX_TOTAL',10),self.assertRaises(ValueError):PackPreview(archive,self.root/'tmp')
        with patch('companion.packs.MAX_FILES',1),self.assertRaises(ValueError):PackPreview(archive,self.root/'tmp')
    def test_install_copy_failure_cleans_only_own_directory(self):
        with PackPreview(self.archive(),self.root/'tmp') as preview:
            base=self.root/'a/packs';base.mkdir(parents=True);keep=base/'unrelated';keep.mkdir();(keep/'file').write_text('keep')
            with patch('companion.packs.shutil.copytree',side_effect=OSError('copy failure')):
                with self.assertRaises(OSError):install_and_use(self.store,preview.pack)
            self.assertEqual(list(base.iterdir()),[keep]);self.assertEqual((keep/'file').read_text(),'keep')
            self.assertEqual(self.store.path.read_bytes(),self.before)
    def test_export_failure_preserves_previous_output(self):
        target=self.archive();before=target.read_bytes();plan=self.plan()
        with patch('companion.packs.shutil.copyfile',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):write_export(plan,target)
        self.assertEqual(target.read_bytes(),before)
    def test_text_only_status_and_missing_rule_preserved(self):
        self.profile['voice_dir']='';archive=self.archive()
        with PackPreview(archive,self.root/'tmp') as preview:
            self.assertEqual(preview.pack.recordings,0);self.assertFalse(preview.pack.complete)
            identifier,_=install_and_use(self.store,preview.pack)
            profile=self.store.profile(identifier)
            self.assertEqual(len(profile['rules']),1);self.assertFalse(profile['use_bundled_demo'])
            self.assertEqual(candidates(profile,profile['rules'][0]),[])
    def test_relative_temp_path_is_supported(self):
        relative=(self.root/'relative').relative_to(ROOT)
        with PackPreview(self.archive(),relative) as preview:self.assertTrue(preview.pack.complete)
    def test_unavailable_extension_events_are_retained_but_disabled(self):
        self.profile['rules'][0]['event']='external_test_event'
        with PackPreview(self.archive(),self.root/'tmp') as preview:
            identifier,_=install_and_use(self.store,preview.pack)
            self.assertEqual(self.store.profile(identifier)['rules'][0]['event'],'external_test_event')
            self.assertFalse(self.store.profile(identifier)['rules'][0]['enabled'])
            identifier,_=install_and_use(self.store,preview.pack,available_events={'external_test_event'})
            self.assertTrue(self.store.profile(identifier)['rules'][0]['enabled'])
    def test_known_tts_reference_is_excluded_from_random_folder_export(self):
        clip=self.voice/'test/hello-model.wav'
        config={'tts':dict(project=str(self.voice),reference='test/hello-model.wav')}
        plan=self.plan(excluded_sources=reference_sources(config))
        self.assertEqual(plan.sources,{})
        with PackPreview(write_export(plan,self.root/'without-reference.wcpak'),self.root/'tmp') as preview:
            self.assertFalse(preview.pack.complete);self.assertEqual(preview.pack.recordings,0)
            self.assertNotIn(str(clip),json.dumps(preview.pack.manifest,ensure_ascii=False))
    def test_import_provisions_empty_optional_channels(self):
        for selected in (None,[]):
            archive=write_export(self.plan(),self.root/'channels.wcpak',selected)
            with PackPreview(archive,self.root/'tmp') as preview:
                identifier,_=install_and_use(self.store,preview.pack)
                profile=self.store.profile(identifier)
                self.assertTrue(Path(profile['voice_dir']).is_dir())
                self.assertTrue(Path(profile['bgm_dir']).is_dir())
                self.assertFalse(list(Path(profile['bgm_dir']).iterdir()))
                validate_directory(Path(profile['voice_dir']).parent)
    def test_existing_empty_pack_channel_repair_keeps_inventory_unchanged(self):
        with PackPreview(write_export(self.plan(),self.root/'text.wcpak',[]),self.root/'tmp') as preview:
            identifier,_=install_and_use(self.store,preview.pack)
        profile=self.store.profile(identifier);voice=Path(profile['voice_dir']);bgm=Path(profile['bgm_dir']);base=voice.parent
        before={f.name:f.read_bytes() for f in base.iterdir() if f.is_file()}
        voice.rmdir();bgm.rmdir()
        created=ensure_pack_channels(self.store,profile)
        self.assertEqual(set(created),{voice,bgm})
        self.assertEqual({f.name:f.read_bytes() for f in base.iterdir() if f.is_file()},before)
        self.assertFalse(ensure_pack_channels(self.store,profile))
    def test_repair_never_creates_custom_or_unowned_paths(self):
        with PackPreview(self.archive(),self.root/'tmp') as preview:
            identifier,_=install_and_use(self.store,preview.pack)
        profile=copy.deepcopy(self.store.profile(identifier));custom=self.root/'custom-missing'
        profile['voice_dir']=str(custom)
        self.assertEqual(ensure_pack_channels(self.store,profile),[])
        self.assertFalse(custom.exists())
        profile['pack_install']='../outside'
        self.assertEqual(ensure_pack_channels(self.store,profile),[])
    def test_failed_reuse_save_removes_only_new_empty_channel(self):
        with PackPreview(self.archive(),self.root/'tmp') as preview:
            identifier,_=install_and_use(self.store,preview.pack)
            profile=self.store.profile(identifier);bgm=Path(profile['bgm_dir']);bgm.rmdir()
            before=copy.deepcopy(self.store.config);voice=Path(profile['voice_dir'])/'test/hello-model.wav';audio=digest(voice)
            with patch.object(self.store,'save',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):install_and_use(self.store,preview.pack)
            self.assertFalse(bgm.exists());self.assertEqual(self.store.config,before);self.assertEqual(digest(voice),audio)
    def test_failed_channel_repair_rolls_back_partial_creation(self):
        with PackPreview(write_export(self.plan(),self.root/'text.wcpak',[]),self.root/'tmp') as preview:
            identifier,_=install_and_use(self.store,preview.pack)
        profile=self.store.profile(identifier);voice=Path(profile['voice_dir']);bgm=Path(profile['bgm_dir']);voice.rmdir();bgm.rmdir()
        mkdir=Path.mkdir
        def fail(path,*args,**kwargs):
            if path==bgm:raise OSError('simulated channel creation failure')
            return mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',fail),self.assertRaises(OSError):ensure_pack_channels(self.store,profile)
        self.assertFalse(voice.exists());self.assertFalse(bgm.exists())
    def test_export_can_run_without_qt(self):
        # Core exporting imports pure operation lookup, never GUI or service code.
        import ast
        source=(ROOT/'companion/packs.py').read_text(encoding='utf-8-sig')
        modules=[n.module for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any(m and ('PySide6' in m or m.endswith('_ui') or m.endswith('operation_voices')) for m in modules))

if __name__=='__main__':unittest.main()
