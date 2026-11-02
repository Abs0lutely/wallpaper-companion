import unittest
import tempfile
from pathlib import Path
from companion.voice_locales import switch_operation_categories,migrate_categories,legacy_candidates,translated_lines
from companion.operation_rules import default_rules
from test_core import TEST_TEMP,wav_bytes

class VoiceLocalesTests(unittest.TestCase):
    def test_bulk_switch_preserves_custom_and_playback_settings(self):
        rules=default_rules();rules[0].update(category="Custom",enabled=False,cooldown=9)
        switched,count=switch_operation_categories(rules,"ja-JP")
        self.assertEqual(count,25)
        self.assertEqual(switched[0],rules[0])
        self.assertTrue(all(r["category"].endswith("·ja-JP") for r in switched[1:]))
        self.assertEqual(switch_operation_categories(switched,"ja-JP")[1],0)
        self.assertFalse(rules[1]["category"].endswith("·ja-JP"))

    def test_migration_only_known_text_in_legacy_category(self):
        e=dict(translated_lines("starter","ja-JP")[0]);e["category"]=e["category"].rsplit("·",1)[0]
        custom={**e,"category":"My custom category"}
        new,changes=migrate_categories([e,custom])
        self.assertEqual(len(changes),1)
        self.assertTrue(new[0]["category"].endswith("·ja-JP"))
        self.assertEqual(new[1],custom)

    def test_legacy_lookup_filters_out_other_languages(self):
        from companion.core import filename_for,candidates,new_profile,new_rule
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            entry=translated_lines("starter","ja-JP")[0]
            folder=Path(tmp)/entry["category"].rsplit("·",1)[0];folder.mkdir()
            ja=folder/filename_for(entry["text"],"Model");ja.write_bytes(wav_bytes())
            (folder/"中文音频.wav").write_bytes(wav_bytes())
            self.assertEqual(legacy_candidates(tmp,entry["category"]),[ja])
            p=new_profile();p["voice_dir"]=tmp
            r=new_rule();r["source"]=entry["category"]
            self.assertEqual(candidates(p,r),[ja])

    def test_japanese_pack_is_complete_and_operation_rules_discover_it(self):
        from companion.bundled_audio import validate_bundled_manifest,bundled_root,validate_starter_pack
        from companion.operation_voices import scan_clips
        from companion.core import ROOT
        audio_root=ROOT/"examples/audio"
        manifest=validate_bundled_manifest(audio_root)
        self.assertEqual(len(manifest["files"]),180)
        self.assertEqual(sum(e.get("locale")=="ja-JP" for e in manifest["files"]),90)
        self.assertEqual(len(validate_starter_pack(audio_root/"starter-voice-ja-JP")["files"]),38)
        rules,_=switch_operation_categories(default_rules(),"ja-JP")
        clips=scan_clips([audio_root/"operation-voice-ja-JP"],rules)
        self.assertEqual(len(clips),26)
        self.assertTrue(all(len(files)==2 for files in clips.values()))
