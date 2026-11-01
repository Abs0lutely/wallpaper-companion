import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from companion.core import Store
from companion.i18n import language, normalize_language, set_language, tr
from test_core import TEST_TEMP


class LanguageTests(unittest.TestCase):
    def tearDown(self):
        set_language("zh-CN")

    def test_invalid_language_falls_back_without_losing_config(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            path = Path(tmp) / "config.json"
            for value in (None, "xx", [], 12, {}):
                path.write_text(json.dumps(dict(ui_language=value, profiles=[], monitor=3)), encoding="utf-8")
                store = Store(path)
                self.assertEqual(store.config["ui_language"], "zh-CN")
                self.assertEqual(store.config["monitor"], 3)

    def test_old_and_saved_config(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            path = Path(tmp) / "config.json"
            store = Store(path)
            self.assertEqual(store.config["ui_language"], "zh-CN")
            store.config["ui_language"] = "en-US"
            store.save()
            self.assertEqual(Store(path).config["ui_language"], "en-US")
            self.assertEqual(language(), "zh-CN")

    def test_translation_fallback_and_named_parameters(self):
        set_language("en-US")
        self.assertIn("next time", tr("settings.language_next_start", "fallback"))
        self.assertEqual(tr("unknown", "保留 {name}", name="原始名称"), "保留 原始名称")
        set_language("zh-CN")
        self.assertEqual(tr("settings.language", "中文"), "中文")
