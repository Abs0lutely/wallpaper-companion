import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verify_upgrades


class UpgradeVerificationTests(unittest.TestCase):
    def test_supported_baselines(self):
        self.assertEqual(verify_upgrades.parse_args([]).baseline, "v0.11.0")
        self.assertEqual(verify_upgrades.parse_args(["--baseline", "v0.12.0"]).baseline, "v0.12.0")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            verify_upgrades.parse_args(["--baseline", "../personal"])

    def test_refuses_local_installation_before_touching_files(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}), patch("sys.argv", ["verify_upgrades.py"]):
            with patch.object(verify_upgrades, "check_assets") as assets:
                with self.assertRaisesRegex(RuntimeError, "disposable Windows"):
                    verify_upgrades.main()
                assets.assert_not_called()

    def test_baseline_assets_reject_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ["old-portable.zip", "old-setup.exe"]
            for name in names:
                (root / name).write_bytes(b"verified fixture")
            (root / "SHA256SUMS.txt").write_text("".join(
                f"{verify_upgrades.digest(root / name)}  {name}\n" for name in names))
            self.assertEqual(verify_upgrades.check_assets(root), [(root / name).resolve() for name in names])
            (root / names[0]).write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "incorrect release asset"):
                verify_upgrades.check_assets(root)
