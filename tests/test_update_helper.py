import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from companion.program_update import digest, personal_snapshot
from companion.update_helper import apply_plan, run_plan, wait_for_parent
from test_core import TEST_TEMP


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(dir=TEST_TEMP)
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.target = self.root / "app 中文 space"
        self.target.mkdir()
        for name, body in {"WallpaperCompanion.exe": "old", "portable.flag": "keep", "app-version.txt": "0.11.0",
                           "shared/voice/a.wav": "personal audio", "data/config.json": "personal settings",
                           "data/packs/p/voice/a.wav": "pack audio", "plugins/keep.py": "plugin"}.items():
            p = self.target / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body)
        self.archive = self.root / "WallpaperCompanion-0.12.0-windows-x64-portable.zip"
        with zipfile.ZipFile(self.archive, "w") as z:
            for name, body in {"WallpaperCompanion.exe": "new", "app-version.txt": "0.12.0", "USER_GUIDE.md": "help",
                               "WallpaperCompanionUpdater.exe": "new helper", "_internal/runtime.dll": "runtime"}.items():
                z.writestr("WallpaperCompanion/" + name, body)
        self.plan = dict(target=str(self.target), archive=str(self.archive), sha256=digest(self.archive),
                         size=self.archive.stat().st_size, version="0.12.0", portable=True,
                         parent_pid=99999999, parent_started=0)

    def test_verified_portable_apply_preserves_personal_files_and_helper(self):
        before = personal_snapshot(self.target)
        with patch("companion.update_helper.running_instances", return_value=[]), patch("companion.program_update.running_instances", return_value=[]):
            result = apply_plan(self.plan)
        self.assertTrue(result["applied"])
        self.assertEqual(personal_snapshot(self.target), before)
        self.assertEqual((self.target / "app-version.txt").read_text(), "0.12.0")
        self.assertEqual((self.target / "WallpaperCompanionUpdater.exe").read_text(), "new helper")
        self.assertEqual((Path(result["backup"]) / "WallpaperCompanion.exe").read_text(), "old")

    def test_modified_archive_running_instance_and_downgrade_block_before_writes(self):
        for cause in ("running", "digest", "version"):
            plan = dict(self.plan)
            if cause == "digest": plan["sha256"] = "0" * 64
            if cause == "version": (self.target / "app-version.txt").write_text("0.13.0")
            with patch("companion.update_helper.running_instances", return_value=[123] if cause == "running" else []):
                with self.assertRaises((ValueError, RuntimeError)): apply_plan(plan)
            self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "old")

    def test_installer_uses_existing_directory_without_closing_apps(self):
        (self.target / "portable.flag").unlink()
        archive = self.root / "WallpaperCompanion-0.12.0-windows-x64-setup.exe"
        archive.write_bytes(b"installer")
        plan = {**self.plan, "portable": False, "archive": str(archive), "size": archive.stat().st_size, "sha256": digest(archive)}
        before = personal_snapshot(self.target)
        def installer(command, **kwargs):
            self.assertIn("/DIR=" + str(self.target.resolve()), command)
            self.assertIn("/NOCLOSEAPPLICATIONS", command)
            self.assertIn("/NOFORCECLOSEAPPLICATIONS", command)
            self.assertIn("/NORESTART", command)
            (self.target / "app-version.txt").write_text("0.12.0")
            return SimpleNamespace(returncode=0)
        with patch("companion.update_helper.running_instances", return_value=[]):
            self.assertTrue(apply_plan(plan, installer_runner=installer)["applied"])
        self.assertEqual(before, personal_snapshot(self.target))

    def test_failed_installer_is_reported_and_files_retained(self):
        (self.target / "portable.flag").unlink()
        archive = self.root / "WallpaperCompanion-0.12.0-windows-x64-setup.exe"; archive.write_bytes(b"installer")
        plan = {**self.plan, "portable": False, "archive": str(archive), "size": 9, "sha256": digest(archive)}
        with patch("companion.update_helper.running_instances", return_value=[]):
            with self.assertRaises(RuntimeError): apply_plan(plan, installer_runner=lambda *a, **kw: SimpleNamespace(returncode=5))
        self.assertTrue(archive.is_file())
        self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "old")

    def test_handoff_failure_records_result_without_restart_or_killing(self):
        path = self.root / "handoff.json"; path.write_text(json.dumps(self.plan))
        with patch("companion.update_helper.wait_for_parent", side_effect=RuntimeError("still running")), patch("companion.update_helper.subprocess.Popen") as launch:
            self.assertEqual(run_plan(path, self.root / "test.json"), 1)
            launch.assert_not_called()
        self.assertFalse(json.loads((self.root / "result.json").read_text(encoding="utf-8"))["success"])
        self.assertEqual((self.target / "WallpaperCompanion.exe").read_text(), "old")

    def test_partially_written_installer_can_retry_same_version_only_after_recorded_failure(self):
        (self.target / "portable.flag").unlink()
        archive = self.root / "WallpaperCompanion-0.12.0-windows-x64-setup.exe"; archive.write_bytes(b"installer")
        plan = {**self.plan, "portable": False, "archive": str(archive), "size": 9, "sha256": digest(archive)}
        def partial_install(*args, **kwargs):
            (self.target / "app-version.txt").write_text("0.12.0")
            return SimpleNamespace(returncode=5)
        with patch("companion.update_helper.running_instances", return_value=[]):
            with self.assertRaises(RuntimeError): apply_plan(plan, installer_runner=partial_install)
            with self.assertRaises(ValueError): apply_plan({**plan, "repair": True})
            failure = dict(success=False, version="0.12.0", target=str(self.target.resolve()), sha256=plan["sha256"])
            (self.root / "result.json").write_text(json.dumps(failure))
            self.assertTrue(apply_plan({**plan, "repair": True}, installer_runner=lambda *a, **kw: SimpleNamespace(returncode=0))["applied"])
            (self.target / "app-version.txt").write_text("0.13.0")
            with self.assertRaises(ValueError): apply_plan({**plan, "repair": True})

    def test_parent_wait_does_not_wait_for_reused_pid(self):
        with patch("companion.update_helper.psutil.Process", return_value=SimpleNamespace(create_time=lambda: 222)):
            wait_for_parent(123, 111, timeout=1)
