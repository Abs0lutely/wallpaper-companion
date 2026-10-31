import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from companion.core import Store, RuleEngine, new_profile, new_rule
from companion.assets import attach_resources
from companion.presets import export_payload, import_payload, read_preset, write_preset, validate_payload
from test_core import TEST_TEMP, wav_bytes


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEST_TEMP)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "app/config.json")
        self.profile = new_profile("分享配置")
        self.voice = self.root / "voice"
        (self.voice / "早晨").mkdir(parents=True)
        self.profile.update(voice_dir=str(self.voice), wallpaper=str(self.root / "private-wallpaper.mp4"), api_key="do-not-share")
        self.profile["rules"][0]["source"] = str(self.voice / "早晨")

    def tearDown(self):
        self.temp.cleanup()

    def test_portable_export_has_rules_dialogues_and_settings_without_paths_or_secrets(self):
        payload, warnings = export_payload([self.profile])
        raw = json.dumps(payload)
        self.assertNotIn(str(self.root), raw)
        self.assertNotIn("private-wallpaper", raw)
        self.assertNotIn("do-not-share", raw)
        self.assertEqual(payload["profiles"][0]["rules"][0]["source"], "早晨")
        self.assertEqual(len(payload["profiles"][0]["dialogues"]), 38)
        self.assertEqual(warnings, [])
        path = self.root / "preset.json"
        write_preset(path, [self.profile])
        imported = import_payload(self.store, read_preset(path))
        result = self.store.profile(imported["profile_ids"][0])
        self.assertEqual(result["wallpaper"], "")
        self.assertTrue(Path(result["voice_dir"]).is_dir())
        self.assertNotEqual(result["rules"][0]["id"], self.profile["rules"][0]["id"])
        self.assertEqual(result["rules"][0]["source"], "早晨")

    def test_replacement_preserves_binding_and_audio_without_writing_shared_text(self):
        target = attach_resources(new_profile("当前壁纸", "existing.pkg"), self.root / "shared")
        self.store.config["profiles"] = [target]
        shared_file = Path(target["dialogue_file"])
        before = shared_file.read_bytes()
        payload, _ = export_payload([self.profile])
        payload["profiles"][0]["dialogues"][0]["text"] = "导入的新文本"
        import_payload(self.store, payload, target["id"])
        updated = self.store.profile(target["id"])
        self.assertEqual(updated["wallpaper"], "existing.pkg")
        self.assertEqual(updated["voice_dir"], target["voice_dir"])
        self.assertEqual(updated["name"], target["name"])
        self.assertEqual(updated["dialogue_file"], "")
        self.assertEqual(updated["dialogues"][0]["text"], "导入的新文本")
        self.assertEqual(shared_file.read_bytes(), before)

    def test_invalid_import_never_changes_store_or_creates_resources(self):
        payload, _ = export_payload([self.profile])
        before = copy.deepcopy(self.store.config)
        for source in ["../outside", r"C:\private\audio.wav", "https://remote/audio.wav", "/absolute"]:
            bad = copy.deepcopy(payload)
            bad["profiles"][0]["rules"][0]["source"] = source
            with self.assertRaises(ValueError):
                import_payload(self.store, bad)
            self.assertEqual(self.store.config, before)
            self.assertFalse((self.store.path.parent / "audio").exists())
        bad = copy.deepcopy(payload)
        bad["profiles"][0]["settings"]["bgm_volume"] = 101
        with self.assertRaises(ValueError):
            import_payload(self.store, bad)

    def test_missing_extension_disabled_and_unknown_sensitive_fields_ignored(self):
        payload, _ = export_payload([self.profile])
        payload["profiles"][0]["rules"][0]["event"] = "external_event"
        payload["profiles"][0]["settings"]["api_key"] = "secret"
        payload["enabled_plugins"] = ["untrusted"]
        result = import_payload(self.store, payload)
        profile = self.store.profile(result["profile_ids"][0])
        self.assertFalse(profile["rules"][0]["enabled"])
        self.assertTrue(result["warnings"])
        self.assertNotIn("api_key", profile)
        self.assertEqual(self.store.config["enabled_plugins"], [])

    def test_external_audio_source_export_warns_and_omits_absolute_location(self):
        self.profile["rules"][0]["source"] = str(self.root / "outside/hello.wav")
        payload, warnings = export_payload([self.profile])
        self.assertTrue(warnings)
        self.assertEqual(payload["profiles"][0]["rules"][0]["source"], "hello.wav")

    def test_size_and_schema_limits(self):
        path = self.root / "huge.json"
        path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
        with self.assertRaises(ValueError): read_preset(path)
        payload, _ = export_payload([self.profile])
        payload["version"] = 99
        with self.assertRaises(ValueError): validate_payload(payload)

    def test_hidden_fields_are_validated_even_for_non_keyboard_rules(self):
        payload, _ = export_payload([self.profile])
        payload["profiles"][0]["rules"][0]["event"] = "mouse_middle"
        for field, value in [("hotkey", {}), ("at", []), ("at", "25:00")]:
            bad = copy.deepcopy(payload)
            bad["profiles"][0]["rules"][0][field] = value
            with self.assertRaises(ValueError): validate_payload(bad)


class ScheduledRuleTests(unittest.TestCase):
    def test_fixed_time_fires_once_and_survives_profile_resets(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
            root = Path(temp)
            (root / "hello.wav").write_bytes(wav_bytes())
            profile = new_profile()
            profile["voice_dir"] = str(root)
            rule = new_rule("scheduled", "每天九点")
            rule.update(at="09:00", cooldown=0)
            profile["rules"] = [rule]
            engine = RuleEngine()
            self.assertIsNone(engine.choose(profile, "scheduled", now=0, clock=datetime(2026, 10, 31, 8, 59)))
            self.assertIsNotNone(engine.choose(profile, "scheduled", now=10, clock=datetime(2026, 10, 31, 9)))
            self.assertIsNone(engine.choose(profile, "scheduled", now=30, clock=datetime(2026, 10, 31, 9, 0, 30)))
            engine.reset()
            self.assertIsNone(engine.choose(profile, "scheduled", now=40, clock=datetime(2026, 10, 31, 9, 0, 40)))
            self.assertIsNone(engine.choose(profile, "scheduled", now=50, clock=datetime(2026, 10, 31, 9, 1)))
            self.assertIsNotNone(engine.choose(profile, "scheduled", now=90000, clock=datetime(2026, 11, 1, 9)))


if __name__ == "__main__":
    unittest.main()
