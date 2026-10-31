import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.release_local import pipeline


class LocalReleaseTests(unittest.TestCase):
    def exercise(self, fail=None, passed=True, corrupt=False, ready=True, compiler=True, report=True):
        temporary = tempfile.TemporaryDirectory(prefix="release 流程 ")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        stage, final, work = root / "stage", root / "verified", root / "work"
        compiler_path = root / "build/tools/inno/ISCC.exe"
        if compiler:
            compiler_path.parent.mkdir(parents=True)
            compiler_path.touch()
        commands = []

        def run(command):
            commands.append(command)
            if fail and fail in command:
                raise RuntimeError("simulated failed step")
            if "scripts/build_windows.py" in command:
                stage.mkdir()
                names = ["WallpaperCompanion-1.2.3-windows-x64-portable.zip", "WallpaperCompanion-1.2.3-windows-x64-setup.exe"]
                for name in names:
                    (stage / name).write_bytes(b"test package")
                (stage / "SHA256SUMS.txt").write_text("".join(
                    f"{hashlib.sha256((stage / n).read_bytes()).hexdigest()}  {n}\n" for n in names))
            if "scripts/verify_windows.py" in command:
                reports = work / "verification"
                reports.mkdir(parents=True)
                if report:
                    (reports / "release-verification.json").write_text(json.dumps({"passed": passed}))
                if corrupt:
                    next(stage.glob("*.zip")).write_bytes(b"changed")

        try:
            pipeline(root, work, stage, final, run, ready=lambda _: ready)
        except Exception:
            self.assertFalse(final.exists(), "Failed runs must not expose verified artifacts")
            raise
        return final, commands

    def test_pass_promotes_exactly_three_artifacts(self):
        final, commands = self.exercise()
        self.assertEqual(len(list(final.iterdir())), 3)
        self.assertFalse(any("install" in c for c in commands))
        self.assertEqual(commands[-1][1], "scripts/verify_windows.py")

    def test_dependency_setup_when_missing(self):
        _, commands = self.exercise(ready=False)
        self.assertEqual(commands[0][1:4], ["-m", "pip", "install"])

    def test_compiler_setup_when_missing(self):
        _, commands = self.exercise(compiler=False)
        self.assertTrue(any("scripts/bootstrap_inno.ps1" in c for c in commands))

    def test_missing_report_does_not_promote(self):
        with self.assertRaises(FileNotFoundError):
            self.exercise(report=False)

    def test_source_failure_stops_before_build(self):
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.exercise(fail="unittest")

    def test_build_failure_does_not_promote(self):
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.exercise(fail="scripts/build_windows.py")

    def test_verifier_failure_does_not_promote(self):
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.exercise(fail="scripts/verify_windows.py")

    def test_false_report_does_not_promote(self):
        with self.assertRaisesRegex(RuntimeError, "did not pass"):
            self.exercise(passed=False)

    def test_changed_bytes_do_not_promote(self):
        with self.assertRaisesRegex(RuntimeError, "changed after verification"):
            self.exercise(corrupt=True)
