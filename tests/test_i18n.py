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

    def test_catalog_keys_and_format_parameters_match_sources(self):
        import string
        from companion.translations_en import EN, SOURCES
        parse = lambda text: {(field, spec, conversion) for _, field, spec, conversion in string.Formatter().parse(text) if field is not None}
        self.assertGreater(len(SOURCES), 1000)
        for key, source in SOURCES.items():
            self.assertIn(key, EN)
            self.assertTrue(EN[key])
            self.assertEqual(parse(source), parse(EN[key]), key)

    def test_all_builtin_translation_calls_have_catalog_entries(self):
        import ast
        from companion.translations_en import EN, SOURCES
        root = Path(__file__).resolve().parents[1]
        for path in [*root.joinpath("companion").glob("*.py"), root / "main.py"]:
            if path.name == "translations_en.py":
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" and isinstance(node.args[0], ast.Constant):
                    key = node.args[0].value
                    source = node.args[1].value
                    self.assertIn(key, EN, (path, node.lineno))
                    self.assertEqual(source, SOURCES[key], (path, node.lineno))

    def test_language_never_changes_existing_content_or_model_names(self):
        from companion.core import new_profile
        from companion.audio_names import infer_model_label
        from companion.dialogues import starter_dialogues, dialogue_rules
        from companion.operation_rules import default_rules as operation_rules
        without_ids = lambda rules: [{k:v for k,v in r.items() if k != "id"} for r in rules]
        original = starter_dialogues(), without_ids(dialogue_rules()), operation_rules()
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            store=Store(Path(tmp)/"config.json")
            p=new_profile("用户角色")
            store.config["profiles"]=[p]
            for locale in ("en-US", "zh-CN"):
                set_language(locale)
                self.assertEqual(infer_model_label({}, "gpt_sovits"), "未指定模型")
                self.assertEqual(infer_model_label({"sovits_weights":"角色.pth"}, "gpt_sovits"), "角色")
                store.config["ui_language"]=locale
                store.save()
                self.assertEqual(Store(store.path).profile(p["id"]),p)
                self.assertEqual((starter_dialogues(),without_ids(dialogue_rules()),operation_rules()), original)
