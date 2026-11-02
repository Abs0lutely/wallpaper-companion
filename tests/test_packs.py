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

if __name__=='__main__':unittest.main()
