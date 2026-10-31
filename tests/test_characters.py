import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml

from companion.characters import scan_models, save_character, delete_character, reference_transcript, normalize_characters
from companion.core import Store
from companion.sovits_config import model_key, runtime_config


class CharacterTests(unittest.TestCase):
    def test_malformed_presets_are_rejected_without_accessing_models(self):
        for entries in [{}, [dict(id="x", name="a", settings={"speed": "fast"})], [dict(id="x", name="a", settings=[])]]:
            with self.assertRaises(ValueError):
                normalize_characters(entries)
    def fixture(self, root):
        (root / "api_v2.py").touch()
        folder = root / "models/v2ProPlus/角色A"
        folder.mkdir(parents=True)
        for file in ("voice-e20.ckpt", "voice_e20_s100.pth", "参考.wav"):
            (folder / file).write_bytes(b"fixture")
        return dict(project=str(root), gpt_weights="models/v2ProPlus/角色A/voice-e20.ckpt",
            sovits_weights="models/v2ProPlus/角色A/voice_e20_s100.pth", reference="models/v2ProPlus/角色A/参考.wav",
            prompt="参考原文。", text_lang="zh", prompt_lang="zh", speed=1.2, url="http://127.0.0.1:9880")

    def test_scan_pairs_by_name_and_version_without_opening_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            for folder in (root / "runtime", root / "GPT_SoVITS/pretrained_models"):
                folder.mkdir(parents=True)
                (folder / "junk.ckpt").write_bytes(b"not a pickle")
            result = scan_models(root)
            self.assertEqual(len(result["models"]), 2)
            self.assertEqual(len(result["pairs"]), 1)
            self.assertEqual(result["pairs"][0]["name"], "角色A")
            self.assertEqual(result["pairs"][0]["version"], "v2ProPlus")
            self.assertEqual(len(result["references"]), 1)

    def test_ambiguous_or_different_version_models_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = self.fixture(root)
            (root / settings["gpt_weights"]).with_name("voice-e30.ckpt").write_bytes(b"another")
            for folder, file in [("GPT_weights_v3", "b-e1.ckpt"), ("SoVITS_weights_v4", "b_e1.pth")]:
                (root / folder).mkdir(); (root / folder / file).write_bytes(b"fixture")
            result = scan_models(root)
            self.assertEqual(result["pairs"], [])
            self.assertTrue(result["warnings"])

    def test_presets_persist_full_character_without_credentials_and_delete_only_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = self.fixture(root)
            store = Store(root / "app/config.json")
            with patch("companion.managed_api.api") as api:
                item = save_character(store, "角色A", {**settings, "api_key": "must-not-store"})
                restored = Store(store.path)
                self.assertEqual(restored.config["tts_characters"][0]["settings"]["prompt"], settings["prompt"])
                self.assertEqual(restored.config["tts"]["gpt_weights"], settings["gpt_weights"])
                self.assertEqual(restored.config["tts_character"], item["id"])
                self.assertNotIn("must-not-store", store.path.read_text(encoding="utf-8"))
                delete_character(store, item["id"])
                api.ensure.assert_not_called(); api.synthesize.assert_not_called()
            self.assertEqual(Store(store.path).config["tts_characters"], [])
            self.assertTrue((root / settings["gpt_weights"]).is_file())
            self.assertTrue((root / settings["reference"]).is_file())

    def test_failed_preset_save_rolls_back_and_incomplete_pair_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = self.fixture(root)
            store = Store(root / "app/config.json")
            before = store.config
            with patch.object(store, "save", side_effect=OSError("fixture")):
                with self.assertRaises(OSError):
                    save_character(store, "a", settings)
            self.assertIs(store.config, before)
            with self.assertRaises(ValueError):
                save_character(store, "a", {**settings, "sovits_weights": ""})

    def test_transcript_only_reads_matching_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = self.fixture(root)
            (root / "unrelated.txt").write_text("不能猜这段", encoding="utf-8")
            with self.assertRaises(ValueError):
                reference_transcript(settings)
            (root / settings["reference"]).with_suffix(".lab").write_text("逐字原文", encoding="utf-8")
            self.assertEqual(reference_transcript(settings), "逐字原文")

    def test_runtime_config_overrides_models_and_keeps_original_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = self.fixture(root)
            source = root / "GPT_SoVITS/configs/tts_infer.yaml"
            source.parent.mkdir(parents=True)
            source.write_text("custom:\n  version: v2\n  device: cpu\n  is_half: false\n  t2s_weights_path: old.ckpt\n  vits_weights_path: old.pth\n", encoding="utf-8")
            before = source.read_bytes()
            private = runtime_config(settings, root / "data")
            config = yaml.safe_load(private.read_text(encoding="utf-8"))["custom"]
            self.assertEqual(config["t2s_weights_path"], str((root / settings["gpt_weights"]).resolve()))
            self.assertEqual(config["version"], "v2ProPlus")
            self.assertEqual(config["device"], "cpu")
            self.assertEqual(source.read_bytes(), before)
            with self.assertRaises(ValueError):
                runtime_config(settings, root / "protected", [root / "protected"])

    def test_empty_or_missing_models_fail_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); settings = self.fixture(root)
            (root / settings["gpt_weights"]).write_bytes(b"")
            with self.assertRaises(ValueError):
                model_key(settings)
