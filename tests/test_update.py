import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.update_portable import stage_update, apply_update, digest, personal_snapshot
from test_core import TEST_TEMP


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(dir=TEST_TEMP)
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.target = self.root / "portable"
        self.target.mkdir()
        for name, content in {"portable.flag": "portable", "WallpaperCompanion.exe": "old exe", "_internal/old.dll": "old dll",
                              "data/config.json": '{"profiles":[{"id":"keep"}]}', "data/audio/line.wav": "user audio",
                              "shared/voice/keep.wav": "shared user audio", "shared/dialogues.json": "shared user lines",
                              "plugins/custom.py": "user plugin", "迁移记录/backup.json": "original", "extra-audio/music.mp3": "external"}.items():
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.archive = self.root / "WallpaperCompanion-0.6.1-windows-x64-portable.zip"
        self.write_archive()

    def write_archive(self, extra=None):
        with zipfile.ZipFile(self.archive, "w") as z:
            for name, content in {"WallpaperCompanion.exe": "new exe", "_internal/new.dll": "new dll",
                                  "USER_GUIDE.md": "new manual", "portable.flag": "changed marker", **(extra or {})}.items():
                z.writestr("WallpaperCompanion/" + name, content)

    def stage(self):
        return stage_update(self.archive, self.target, digest(self.archive))

    def test_stage_does_not_change_running_program_or_user_data(self):
        before = personal_snapshot(self.target)
        self.assertTrue(self.stage().is_file())
        self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "old exe")
        self.assertEqual(before, personal_snapshot(self.target))

    def test_apply_preserves_configuration_audio_plugins_marker_and_backups(self):
        before = personal_snapshot(self.target)
        plan = self.stage()
        with patch("scripts.update_portable.running_instances", return_value=[]):
            result = apply_update(plan, self.target)
        self.assertTrue(result["personal_files_preserved"])
        self.assertEqual(before, personal_snapshot(self.target))
        self.assertEqual((self.target / "portable.flag").read_text(), "portable")
        self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "new exe")
        self.assertFalse((self.target / "_internal/old.dll").exists())
        self.assertEqual((Path(result["backup"]) / "_internal/old.dll").read_text(), "old dll")

    def test_running_application_blocks_apply_without_killing_or_overwriting(self):
        plan = self.stage()
        with patch("scripts.update_portable.running_instances", return_value=[123]):
            with self.assertRaises(RuntimeError):
                apply_update(plan, self.target)
        self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "old exe")

    def test_archive_cannot_overwrite_user_configuration_or_escape(self):
        for name in ["data/config.json", "plugins/custom.py", "../../escape.txt"]:
            self.write_archive({name: "malicious"})
            with self.assertRaises(ValueError):
                self.stage()
        self.assertFalse((self.root / "escape.txt").exists())

    def test_modified_staged_binary_is_rejected(self):
        plan = self.stage()
        (plan.parent / "payload/WallpaperCompanion.exe").write_text("corrupted")
        with patch("scripts.update_portable.running_instances", return_value=[]):
            with self.assertRaises(ValueError):
                apply_update(plan, self.target)
        self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "old exe")

    def test_failed_file_replacement_rolls_back_program(self):
        plan = self.stage()
        original = Path.rename
        def fail_new_exe(path, destination):
            if path == plan.parent / "payload/WallpaperCompanion.exe":
                raise OSError("simulated file lock")
            return original(path, destination)
        with patch("scripts.update_portable.running_instances", return_value=[]), patch.object(Path, "rename", fail_new_exe):
            with self.assertRaises(OSError):
                apply_update(plan, self.target)
        self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "old exe")
        self.assertTrue((self.target / "_internal/old.dll").exists())


if __name__ == "__main__":
    unittest.main()
