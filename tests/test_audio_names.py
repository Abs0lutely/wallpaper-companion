import tempfile
import unittest
from pathlib import Path
from companion.audio_names import infer_model_label, matches_any_model
from companion.core import filename_for, ROOT
from companion.services import generate,generation_duplicates
from companion.extensions import SpeechProvider
from test_generation_progress import audio


OUTPUT=ROOT/"output"
OUTPUT.mkdir(exist_ok=True)


class AudioNameTests(unittest.TestCase):
    def test_model_suffix_safe_long_names_and_legacy_matching(self):
        self.assertEqual(filename_for("你好","神里绫华"),"你好-神里绫华.wav")
        for text,model in [("长台词"*100,"长模型"*50),("含-连字符的台词","模型-A"),("A/B:内容","../模型*名称")]:
            name=filename_for(text,model)
            self.assertLessEqual(len(Path(name).stem),70)
            self.assertNotIn("/",name)
            self.assertNotIn("\\",name)
            self.assertTrue(matches_any_model(Path(name).stem,text))
            self.assertTrue(matches_any_model(Path(name).stem+" (2)",text))
        self.assertTrue(matches_any_model("你好","你好"))
        self.assertFalse(matches_any_model("其他台词-模型","你好"))

    def test_model_inference_and_stale_character_prevention(self):
        settings=dict(project="project",gpt_weights="角色.ckpt",sovits_weights="角色.pth")
        character=dict(name="神里绫华",settings=dict(settings))
        self.assertEqual(infer_model_label(settings,"gpt_sovits",character),"神里绫华")
        self.assertEqual(infer_model_label({**settings,"sovits_weights":"派蒙.pth"},"gpt_sovits",character),"派蒙")
        self.assertEqual(infer_model_label(dict(model="模型",voice="音色"),"openai_compatible"),"模型-音色")
        self.assertEqual(infer_model_label({},"gpt_sovits"),"未指定模型")

    def test_distinct_models_generate_separately_and_same_model_skips(self):
        calls=[]
        provider=SpeechProvider("fixture","fixture",[],lambda settings,text:calls.append(text) or audio(),lambda _:"ok")
        with tempfile.TemporaryDirectory(dir=OUTPUT) as tmp:
            a=generate({"_filename_model":"模型A"},["你好"],tmp,provider=provider,skip_existing=True)
            self.assertEqual(Path(a[0]).name,"你好-模型A.wav")
            self.assertEqual(len(generation_duplicates(["你好"],tmp,model_name="模型A")),1)
            self.assertEqual(generation_duplicates(["你好"],tmp,model_name="模型B"),[])
            b=generate({"_filename_model":"模型B"},["你好"],tmp,provider=provider,skip_existing=True)
            self.assertEqual(Path(b[0]).name,"你好-模型B.wav")
            self.assertEqual(generate({"_filename_model":"模型A"},["你好"],tmp,provider=provider,skip_existing=True),[])
            self.assertEqual(len(calls),2)
            (Path(tmp)/"旧台词.wav").write_bytes(audio())
            self.assertEqual(len(generation_duplicates(["旧台词"],tmp,model_name="模型B")),1)

    def test_operation_scanner_accepts_named_models(self):
        from companion.action_lines import EVENT_LINES
        from companion.operation_voices import scan_clips
        with tempfile.TemporaryDirectory(dir=OUTPUT) as tmp:
            category,lines=EVENT_LINES["save"]
            folder=Path(tmp)/category; folder.mkdir()
            name=folder/filename_for(lines[0],"神里绫华");name.write_bytes(audio())
            self.assertEqual(scan_clips([tmp])["save"],[str(name)])

    def test_distribution_manifest_accepts_model_names_without_rewriting_assets(self):
        import hashlib,json
        from companion.bundled_audio import validate_starter_pack,validate_bundled_manifest
        from companion.dialogues import starter_dialogues
        entry=starter_dialogues()[0]
        with tempfile.TemporaryDirectory(dir=OUTPUT) as tmp:
            root=Path(tmp); starter=root/"starter-voice"
            file=starter/entry["category"]/filename_for(entry["text"],"神里绫华"); file.parent.mkdir(parents=True)
            import wave
            with wave.open(str(file),"wb") as sound:
                sound.setparams((1,2,16000,0,"NONE","not compressed")); sound.writeframes(b"\x01\x00"*1600)
            record=dict(category=entry["category"],text=entry["text"],filename=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            (starter/"manifest.json").write_text(json.dumps(dict(format="wallpaper-companion-starter-audio",version=1,files=[record])),encoding="utf-8")
            (root/"manifest.json").write_text(json.dumps(dict(format="wallpaper-companion-bundled-audio",version=1,files=[dict(pack="starter-voice",**record)])),encoding="utf-8")
            self.assertEqual(validate_starter_pack(starter)["files"][0]["filename"],file.name)
            self.assertEqual(len(validate_bundled_manifest(root)["files"]),1)
