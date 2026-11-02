"""Public text packs stay complete, importable and routable without live TTS."""
import json
from pathlib import Path
import tempfile
import unittest

from companion.action_lines import operation_dialogues
from companion.core import ROOT
from companion.dialogues import normalize_dialogues, starter_dialogues
from companion.extensions import SpeechProvider
from companion.operation_rules import normalize_payload
from companion.operation_voices import scan_clips
from companion.services import generate_dialogue_entries
from test_core import TEST_TEMP, wav_bytes


def read_pack(pack, locale):
    return json.loads((ROOT / f"examples/dialogues/{pack}-{locale}.json").read_text(encoding="utf-8"))


class TranslatedDialogueTests(unittest.TestCase):
    def test_complete_translations_preserve_source_order_and_safe_categories(self):
        for locale in ("en-US", "ja-JP"):
            for pack, source in (("starter", starter_dialogues()), ("operation", operation_dialogues())):
                with self.subTest(locale=locale, pack=pack):
                    translated = read_pack(pack, locale)
                    self.assertEqual(normalize_dialogues(translated), translated)
                    self.assertEqual(len(translated), len(source))
                    self.assertEqual(len({e["id"] for e in translated}), len(source))
                    self.assertEqual(len({e["text"] for e in translated}), len(source))
                    for original, entry in zip(source, translated, strict=True):
                        self.assertEqual(entry["id"].replace(f"_{locale}_", "_"), original["id"])
                        self.assertNotEqual(entry["text"], original["text"])
                        self.assertEqual(entry["category"], original["category"] + f"·{locale}")
                        if locale == "en-US":
                            self.assertTrue(entry["text"].isascii())
                        else:
                            self.assertTrue(any("\u3040" <= c <= "\u30ff" for c in entry["text"]))

    def test_plain_text_versions_match_json_exactly(self):
        for locale in ("en-US", "ja-JP"):
            for pack in ("starter", "operation"):
                lines = (ROOT / f"examples/dialogues/{pack}-{locale}.txt").read_text(encoding="utf-8").splitlines()
                self.assertEqual(lines, [e["text"] for e in read_pack(pack, locale)])

    def test_mock_generation_and_operation_rules_find_translated_filenames(self):
        for locale in ("en-US", "ja-JP"):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory(dir=TEST_TEMP) as temporary:
                root = Path(temporary)
                calls = []
                provider = SpeechProvider("translation-fixture", "Mock speech", [],
                    lambda settings, text: calls.append(text) or wav_bytes(), lambda _: "ready")
                entries = read_pack("starter", locale) + read_pack("operation", locale)
                result = generate_dialogue_entries({"_filename_model": "TestModel"}, entries, root, provider=provider)
                self.assertEqual(len(result["paths"]), 90)
                self.assertEqual(calls, [e["text"] for e in entries])
                # Repeated import/generation must preserve files and skip existing audio.
                again = generate_dialogue_entries({"_filename_model": "TestModel"}, entries, root, provider=provider)
                self.assertEqual(again["skipped"], 90)
                self.assertEqual(len(calls), 90)
                payload = normalize_payload(json.loads((ROOT / f"examples/presets/operation-voice-rules-{locale}.json").read_text(encoding="utf-8")))
                clips = scan_clips([root], payload["rules"])
                self.assertEqual(len(clips), 26)
                self.assertTrue(all(len(files) == 2 for files in clips.values()))
                self.assertTrue(all(rule["category"].endswith(f"·{locale}") for rule in payload["rules"]))
