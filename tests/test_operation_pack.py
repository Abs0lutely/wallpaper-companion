import json
from pathlib import Path
import tempfile
import unittest
import wave
from companion.action_lines import operation_dialogues
from companion.core import ROOT, filename_for
from companion.operation_pack import require_pack, validate_pack


class OperationPackTests(unittest.TestCase):
    def test_public_manifest_matches_builtin_and_has_unique_categories(self):
        entries = json.loads((ROOT / "examples/dialogues/operation-zh-CN.json").read_text(encoding="utf-8"))
        self.assertEqual(entries, operation_dialogues())
        self.assertEqual(len(entries), 52)
        self.assertEqual(len({e["category"] for e in entries}), 26)

    def test_release_gate_and_readable_audio(self):
        (ROOT / "output").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "output") as tmp:
            root = Path(tmp)
            self.assertEqual(len(validate_pack(root)["missing"]), 52)
            with self.assertRaises(ValueError):
                require_pack(root)
            for e in operation_dialogues():
                p = root / e["category"] / filename_for(e["text"])
                p.parent.mkdir(exist_ok=True)
                with wave.open(str(p), "wb") as f:
                    f.setparams((1, 2, 16000, 0, "NONE", "not compressed")); f.writeframes(b"\x01\x00" * 1600)
            self.assertTrue(require_pack(root)["complete"])
            with wave.open(str(p), "wb") as f:
                f.setparams((1, 2, 16000, 0, "NONE", "not compressed")); f.writeframes(b"\x00\x00" * 1600)
            with self.assertRaisesRegex(ValueError, "静音"):
                require_pack(root)

    def test_one_variant_per_action_is_ready_but_not_complete(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "output") as tmp:
            root=Path(tmp)
            for e in operation_dialogues()[::2]:
                p=root/e["category"]/filename_for(e["text"],"模型标签"); p.parent.mkdir()
                with wave.open(str(p),"wb") as f:
                    f.setparams((1,2,16000,0,"NONE","not compressed")); f.writeframes(b"\x01\x00"*1600)
            report=require_pack(root)
            self.assertTrue(report["ready"])
            self.assertFalse(report["complete"])
            self.assertEqual(len(report["missing"]),26)
