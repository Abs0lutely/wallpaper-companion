import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from companion.services import current_wallpaper


class WallpaperPollingTests(unittest.TestCase):
    def fixture(self, root):
        media = root / "first.mp4"; media.touch()
        second = root / "second.mp4"; second.touch()
        config = {"we_dir": str(root), "monitor": 0}
        data = {"fixture-user": {"general": {"wallpaperconfig": {"selectedwallpapers": {
            "Monitor0": {"file": str(media)}, "Monitor1": {"file": str(second)}}}}}}
        (root / "config.json").write_text(json.dumps(data), encoding="utf-8")
        process = dict(exe=str(root / "wallpaper64.exe"), name="wallpaper64.exe")
        return config, process, media, second

    def test_repeated_background_polls_do_not_launch_gui_and_follow_saved_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, process, first, second = self.fixture(root)
            original = (root / "config.json").read_bytes()
            with patch("companion.services.running_wallpaper_processes", return_value=[process]), patch("companion.services.run_external") as run:
                for _ in range(12):
                    self.assertEqual(current_wallpaper(config)["path"], str(first))
                config["monitor"] = 1
                self.assertEqual(current_wallpaper(config)["path"], str(second))
                saved = json.loads(original)
                saved["fixture-user"]["general"]["wallpaperconfig"]["selectedwallpapers"]["Monitor1"]["file"] = str(first)
                (root / "config.json").write_text(json.dumps(saved), encoding="utf-8")
                self.assertEqual(current_wallpaper(config)["path"], str(first))
                run.assert_not_called()

    def test_failed_saved_read_does_not_launch_gui_as_automatic_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, process, _, _ = self.fixture(root)
            (root / "config.json").write_text("{", encoding="utf-8")
            with patch("companion.services.running_wallpaper_processes", return_value=[process]), patch("companion.services.run_external") as run:
                with self.assertRaises(ValueError):
                    current_wallpaper(config)
                run.assert_not_called()

    def test_explicit_command_query_still_works_and_keeps_saved_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, process, first, second = self.fixture(root)
            config["_wallpaper_command_query"] = True
            with patch("companion.services.running_wallpaper_processes", return_value=[process]), patch("companion.services.run_external", return_value=SimpleNamespace(returncode=0, stdout=str(second).encode())) as run:
                self.assertEqual(current_wallpaper(config)["path"], str(second))
                self.assertIn("getWallpaper", run.call_args.args[0])
            with patch("companion.services.running_wallpaper_processes", return_value=[process]), patch("companion.services.run_external", return_value=SimpleNamespace(returncode=0, stdout=b"")):
                self.assertEqual(current_wallpaper(config)["path"], str(first))

    @unittest.skipUnless(sys.platform == "win32", "Windows startup flags")
    def test_background_tool_hides_gui_and_cursor_feedback_without_mutating_options(self):
        from companion.external import popen_external, STARTF_FORCEONFEEDBACK, STARTF_FORCEOFFFEEDBACK
        original = subprocess.STARTUPINFO()
        original.dwFlags = STARTF_FORCEONFEEDBACK | subprocess.STARTF_USESTDHANDLES
        original.wShowWindow = 5
        with patch("companion.external.subprocess.Popen") as launch:
            popen_external(["fixture.exe"], startupinfo=original, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        kwargs = launch.call_args.kwargs
        info = kwargs["startupinfo"]
        self.assertTrue(info.dwFlags & STARTF_FORCEOFFFEEDBACK)
        self.assertFalse(info.dwFlags & STARTF_FORCEONFEEDBACK)
        self.assertTrue(info.dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertTrue(info.dwFlags & subprocess.STARTF_USESTDHANDLES)
        self.assertEqual(info.wShowWindow, subprocess.SW_HIDE)
        self.assertTrue(kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW)
        self.assertTrue(kwargs["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP)
        self.assertEqual(original.wShowWindow, 5)
        self.assertTrue(original.dwFlags & STARTF_FORCEONFEEDBACK)
