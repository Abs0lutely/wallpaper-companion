import tempfile
import unittest
import os
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from companion.runtime import runtime_layout
from companion.startup import startup_command
from test_core import TEST_TEMP


class RuntimeTests(unittest.TestCase):
    def test_installed_data_stays_outside_application_directory(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as directory:
            root = Path(directory)
            layout = runtime_layout(frozen=True, executable=root / "app/app.exe",
                                    environ={"LOCALAPPDATA": str(root / "local")})
            self.assertEqual(layout.app_dir, root / "app")
            self.assertEqual(layout.data_dir, root / "local/WallpaperCompanion")
            self.assertEqual(layout.plugin_dir, layout.data_dir / "plugins")
            self.assertEqual(layout.shared_dir, layout.app_dir / "shared")

    def test_portable_marker_keeps_resources_next_to_executable(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as directory:
            root = Path(directory)
            (root / "portable.flag").touch()
            layout = runtime_layout(frozen=True, executable=root / "app.exe", environ={})
            self.assertTrue(layout.portable)
            self.assertEqual(layout.data_dir, root / "data")
            self.assertEqual(layout.plugin_dir, root / "plugins")
            self.assertEqual(layout.shared_dir, root / "shared")

    def test_source_and_explicit_data_override(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as directory:
            root = Path(directory)
            layout = runtime_layout(frozen=False, source_root=root, environ={})
            self.assertEqual(layout.data_dir, root / "data")
            layout = runtime_layout(frozen=True, executable=root / "app.exe",
                                    environ={"WALLPAPER_COMPANION_DATA": str(root / "test")})
            self.assertEqual(layout.data_dir, root / "test")
            self.assertEqual(layout.shared_dir, root / "test/shared")

    def test_frozen_startup_uses_executable_without_python_script(self):
        with patch("sys.frozen", True, create=True), patch("sys.executable", r"C:\Apps with spaces\WallpaperCompanion.exe"):
            self.assertEqual(startup_command(), '"C:\\Apps with spaces\\WallpaperCompanion.exe" --tray')

    def test_external_environment_excludes_frozen_paths_and_python_injection(self):
        from companion.external import clean_environment
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as directory:
            root = Path(directory)
            with patch("sys.frozen", True, create=True), patch("sys._MEIPASS", str(root / "bundle"), create=True):
                env = clean_environment({"PYTHONPATH": "private", "PYTHONHOME": "private", "_PYI_ARCHIVE_FILE": "private",
                                         "PATH": os.pathsep.join([str(root / "bundle"), str(root / "bundle/Qt"), str(root / "tools")]), "KEEP": "yes"})
            self.assertEqual(env, {"PATH": str(root / "tools"), "KEEP": "yes"})

    @unittest.skipUnless(sys.platform == "win32", "Windows DLL search API")
    def test_external_launch_restores_dll_search_path_after_failure(self):
        from companion.external import popen_external
        calls = []
        def get_directory(size, output):
            output.value = "original-bundle"
            return len(output.value)
        fake = SimpleNamespace(GetDllDirectoryW=get_directory,
                               SetDllDirectoryW=lambda value: (calls.append(value) or True))
        with patch("sys.frozen", True, create=True), patch("ctypes.windll.kernel32", fake), \
                patch("companion.external.subprocess.Popen", side_effect=OSError("launch failed")):
            with self.assertRaises(OSError):
                popen_external(["external.exe"])
        self.assertEqual(calls, [None, "original-bundle"])


if __name__ == "__main__":
    unittest.main()
