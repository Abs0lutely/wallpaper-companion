import io
import tempfile
import unittest
import wave
from pathlib import Path
from companion.core import filename_for
from companion.extensions import SpeechProvider
from companion.services import generate, generate_dialogue_entries


def audio():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b"\x01\x00"*160)
    return stream.getvalue()


class GenerationProgressTests(unittest.TestCase):
    def test_failure_preserves_completed_count_and_prior_audio(self):
        calls, events = [], []
        def synthesize(settings, text):
            calls.append(text)
            if len(calls) == 2:
                raise ValueError("fixture failed")
            return audio()
        provider = SpeechProvider("fixture", "fixture", [], synthesize, lambda _: "ready")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "已保存 1 条"):
                generate({}, ["第一条", "第二条"], tmp, provider=provider, status=events.append)
            self.assertTrue((Path(tmp)/filename_for("第一条")).is_file())
            self.assertEqual(events[-1]["phase"], "failed")
            self.assertEqual(events[-1]["completed"], 1)
            self.assertTrue(all(e["total"] == 2 and e["completed"] <= 1 for e in events))

    def test_categorized_skips_count_as_processed_without_extra_synthesis(self):
        calls, events = [], []
        provider = SpeechProvider("fixture", "fixture", [], lambda _, text: calls.append(text) or audio(), lambda _: "ready")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/"早晨"; folder.mkdir()
            (folder/filename_for("已有")).write_bytes(audio())
            result = generate_dialogue_entries({}, [dict(text="已有", category="早晨"),dict(text="新音频", category="夜间")], tmp, provider=provider, status=events.append)
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(calls, ["新音频"])
            self.assertTrue(any(e["phase"] == "skipped" and e["completed"] == 1 for e in events))
            self.assertEqual(events[-1]["completed"], 2)
            self.assertTrue(all(e["total"] == 2 for e in events))
