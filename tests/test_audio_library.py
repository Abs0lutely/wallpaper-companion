import tempfile
import unittest
from pathlib import Path
from companion.core import Store, new_profile
from companion.assets import attach_resources, shared_root
from companion.audio_library import locations, inventory, copy_audio, destination, recycle_audio


class AudioLibraryTests(unittest.TestCase):
    def test_shared_inventory_deduplicates_files_and_lists_profile_users(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data/config.json")
            one = attach_resources(new_profile("一"), shared_root(store))
            two = attach_resources(new_profile("二"), shared_root(store))
            store.config["profiles"] = [one, two]
            (Path(one["voice_dir"]) / "你好.wav").write_bytes(b"voice")
            records = inventory([source for source in locations(store) if not source.get("read_only")])["records"]
            self.assertEqual(len(records), 1)
            self.assertCountEqual(records[0]["profiles"], [one["id"], two["id"]])
            self.assertEqual(len(records[0]["locations"]), 3)

    def test_copy_collisions_preserve_originals_and_category_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "你好.wav"; source.write_bytes(b"original")
            target = destination(root / "voice", "早安")
            a = copy_audio([source], target)
            b = copy_audio([source], target)
            self.assertNotEqual(a, b)
            self.assertEqual(source.read_bytes(), b"original")
            self.assertEqual(Path(a[0]).read_bytes(), Path(b[0]).read_bytes())
            for category in ["../out", r"..\out", r"C:\out"]:
                with self.assertRaises(ValueError):
                    destination(root, category)

    def test_protected_directory_cannot_receive_copies_or_recycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "keep.wav"; source.write_bytes(b"keep")
            with self.assertRaises(ValueError):
                copy_audio([source], root / "protected", [root])
            calls = []
            with self.assertRaises(ValueError):
                recycle_audio([source], [root], lambda p: calls.append(p))
            self.assertEqual(calls, [])
            self.assertTrue(source.is_file())

    def test_recycle_failure_never_permanently_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "keep.wav"; source.touch()
            with self.assertRaisesRegex(ValueError, "不会降级"):
                recycle_audio([source], trash=lambda _: (False, ""))
            self.assertTrue(source.exists())
