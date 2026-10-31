import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from companion.assets import attach_resources, load_dialogues, write_dialogues
from companion.core import Store, new_profile
from companion.library import apply_bindings, remove_profiles
from companion.original_audio import detect_original_audio, package_entries, should_block_bgm
from companion.startup import startup_command
from test_core import TEST_TEMP


class ResourceTests(unittest.TestCase):
    def test_shared_dialogues_sync_and_bulk_deletion_keeps_all_files(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
            root = Path(temp)
            store = Store(root / "data/config.json")
            records = []
            for index in range(3):
                path = root / f"wallpaper-{index}.pkg"
                path.write_bytes(b"wallpaper")
                records.append(dict(path=str(path), title=str(index)))
            shared = root / "shared"
            result = apply_bindings(store, records, mode="shared_root", asset_dir=str(shared))
            self.assertEqual(result["created"], 3)
            profiles = store.config["profiles"]
            self.assertEqual(len({p["dialogue_file"] for p in profiles}), 1)
            self.assertEqual(len({p["voice_dir"] for p in profiles}), 1)
            entries = load_dialogues(profiles[0])
            entries[0]["text"] = "共享台词修改"
            write_dialogues(profiles[0]["dialogue_file"], entries)
            self.assertEqual(load_dialogues(profiles[1])[0]["text"], "共享台词修改")
            store.config["manual_profile"] = profiles[0]["id"]
            keep_file = shared / "voice/manual.mp3"
            keep_file.write_bytes(b"downloaded")
            self.assertEqual(remove_profiles(store, [p["id"] for p in profiles[:2]]), 2)
            self.assertEqual(store.config["manual_profile"], "")
            self.assertEqual(len(Store(store.path).config["profiles"]), 1)
            self.assertTrue(keep_file.exists())
            self.assertTrue((shared / "dialogues.json").exists())
            self.assertTrue(all(Path(record["path"]).is_file() for record in records))

    def test_separate_resources_have_separate_dialogue_files(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
            root = Path(temp)
            one = attach_resources(new_profile(), root / "one")
            two = attach_resources(new_profile(), root / "two")
            entries = load_dialogues(one)
            entries[0]["text"] = "独立修改"
            write_dialogues(one["dialogue_file"], entries)
            self.assertNotEqual(load_dialogues(one), load_dialogues(two))
            with self.assertRaises(ValueError):
                attach_resources(new_profile(), root / "readonly", [root])


class OriginalAudioTests(unittest.TestCase):
    def test_video_tracks_and_probe_failure_are_distinct(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
            path = Path(temp) / "wallpaper.mp4"
            path.write_bytes(b"fixture")
            settings = dict(ffprobe="fixture-ffprobe")
            for streams, expected in [([], "no"), ([{"codec_type": "audio"}], "yes")]:
                with patch("companion.original_audio.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps({"streams": streams}).encode())) as run:
                    self.assertEqual(detect_original_audio(settings, str(path))["state"], expected)
                    self.assertIn("-select_streams", run.call_args.args[0])
            with patch("companion.original_audio.subprocess.run", side_effect=OSError("probe failed")):
                self.assertEqual(detect_original_audio(settings, str(path))["state"], "unknown")

    def test_package_index_only_is_positive_evidence_not_live_bgm(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
            path = Path(temp) / "scene.pkg"
            def string(value):
                raw = value.encode()
                return struct.pack("<I", len(raw)) + raw
            body = string("PKGV0020") + struct.pack("<I", 2)
            body += string("materials/test.tex") + struct.pack("<II", 0, 0)
            body += string("sounds/bgm.ogg") + struct.pack("<II", 0, 0)
            path.write_bytes(body)
            before = path.read_bytes()
            self.assertIn("sounds/bgm.ogg", package_entries(path))
            self.assertEqual(detect_original_audio({}, str(path))["state"], "possible")
            self.assertEqual(path.read_bytes(), before)
            path.write_bytes(b"unknown-format")
            self.assertEqual(detect_original_audio({}, str(path))["state"], "unknown")

    def test_conflict_policies_and_manual_override(self):
        profile = new_profile()
        for state in ["yes", "possible", "unknown"]:
            self.assertTrue(should_block_bgm(profile, dict(state=state)))
        self.assertFalse(should_block_bgm(profile, dict(state="no")))
        profile["original_audio_policy"] = "detected"
        self.assertFalse(should_block_bgm(profile, dict(state="unknown")))
        profile["original_audio_override"] = "no"
        self.assertFalse(should_block_bgm(profile, dict(state="yes")))
        profile.update(original_audio_policy="allow", original_audio_override="yes")
        self.assertFalse(should_block_bgm(profile, dict(state="yes")))


class StartupTests(unittest.TestCase):
    def test_startup_command_has_windowless_interpreter_absolute_entry_and_tray(self):
        command = startup_command()
        self.assertIn("main.py", command)
        self.assertIn("--tray", command)
        self.assertIn("pythonw.exe", command)
        self.assertLessEqual(len(command), 260)

    def test_startup_registry_backend_only_changes_own_entry(self):
        from companion import startup
        values = {"OtherApp": "keep"}
        class Handle:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def open_key(hive, path, *args):
            self.assertEqual(path, startup.RUN_KEY)
            return Handle()
        def query(handle, name):
            if name not in values: raise FileNotFoundError(name)
            return values[name], 1
        def delete(handle, name):
            if name not in values: raise FileNotFoundError(name)
            del values[name]
        fake = SimpleNamespace(HKEY_CURRENT_USER="current-user", KEY_SET_VALUE=2, REG_SZ=1,
                               OpenKey=open_key, CreateKeyEx=open_key, QueryValueEx=query,
                               SetValueEx=lambda handle, name, reserved, kind, value: values.update({name: value}), DeleteValue=delete)
        with patch.dict("sys.modules", {"winreg": fake}):
            self.assertFalse(startup.startup_enabled())
            startup.set_startup(True)
            self.assertTrue(startup.startup_enabled())
            self.assertIn("--tray", values[startup.VALUE_NAME])
            startup.set_startup(False)
            startup.set_startup(False)
            self.assertEqual(values, {"OtherApp": "keep"})


if __name__ == "__main__":
    unittest.main()
