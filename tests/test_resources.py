import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from companion.assets import shared_root, private_root, channel_resources, load_dialogues, attach_resources
from companion.core import Store, new_profile
from companion.library import apply_bindings


class ResourceModeTests(unittest.TestCase):
    def test_defaults_follow_store_and_mixed_modes_reference_shared_without_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data/config.json")
            p = attach_resources(new_profile(), shared_root(store))
            voice = Path(p["voice_dir"]) / "shared.wav"
            voice.write_bytes(b"keep")
            result = channel_resources(p, shared_root(store), private_root(store, p),
                dict(voice_dir="shared", bgm_dir="private", dialogue_file="private"))
            self.assertEqual(shared_root(store), (Path(tmp) / "data/shared").resolve())
            self.assertEqual(Path(result["voice_dir"]), voice.parent)
            self.assertEqual(Path(result["bgm_dir"]), private_root(store, p) / "bgm")
            self.assertFalse((private_root(store, p) / "voice/shared.wav").exists())
            self.assertEqual(voice.read_bytes(), b"keep")
            self.assertEqual(load_dialogues(result), p["dialogues"])
            custom = channel_resources(p, shared_root(store), Path(tmp) / "my-private",
                dict(voice_dir="private", bgm_dir="private", dialogue_file="private"))
            self.assertEqual(private_root(store, custom), (Path(tmp) / "my-private").resolve())

    def test_preserves_custom_paths_and_validates_all_before_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = attach_resources(new_profile(), root / "old")
            result = channel_resources(p, root / "shared", root / "private",
                dict(voice_dir="custom", bgm_dir="custom", dialogue_file="custom"))
            for key in ("voice_dir", "bgm_dir", "dialogue_file"):
                self.assertEqual(result[key], p[key])
            with self.assertRaises(ValueError):
                channel_resources(p, root / "protected", root / "new",
                    dict(voice_dir="private", bgm_dir="shared", dialogue_file="private"), [root / "protected"])
            self.assertFalse((root / "new").exists())

    def test_batch_can_use_default_shared_root_without_path_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data/config.json")
            record = Path(tmp) / "wallpaper.pkg"; record.touch()
            apply_bindings(store, [dict(path=str(record), title="默认共享")], mode="shared_root")
            profile = store.config["profiles"][0]
            self.assertEqual(Path(profile["asset_dir"]), shared_root(store))
            self.assertTrue(Path(profile["voice_dir"]).is_dir())
            self.assertEqual(Store(store.path).profile(profile["id"])["voice_dir"], profile["voice_dir"])

    def test_installed_default_shared_is_beside_app_without_moving_existing_resources(self):
        from companion.runtime import runtime_layout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = runtime_layout(frozen=True, executable=root / "installed/app.exe", environ={"LOCALAPPDATA": str(root / "local")})
            store = Store(layout.data_dir / "config.json")
            legacy = attach_resources(new_profile("原绑定"), root / "legacy")
            audio = Path(legacy["voice_dir"]) / "保留.wav"
            audio.write_bytes(b"keep")
            store.config["profiles"] = [legacy]
            with patch("companion.runtime.LAYOUT", layout):
                self.assertEqual(shared_root(store), root / "installed/shared")
                self.assertFalse(shared_root(store).exists())
                self.assertEqual(store.config["profiles"][0], legacy)
                store.config["shared_asset_dir"] = str(root / "custom")
                self.assertEqual(shared_root(store), root / "custom")
            self.assertEqual(audio.read_bytes(), b"keep")
