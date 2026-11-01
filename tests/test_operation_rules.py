import copy
import unittest
from companion.operation_rules import FORMAT, config_payload, default_rules, normalize_payload


class OperationRuleTests(unittest.TestCase):
    def test_defaults_and_roundtrip(self):
        value=config_payload({})
        self.assertTrue(value["enabled"])
        self.assertEqual(len(value["rules"]),26)
        self.assertEqual(normalize_payload(value),value)
        import json
        from companion.core import ROOT
        self.assertEqual(json.loads((ROOT/"examples/presets/operation-voice-rules.json").read_text(encoding="utf-8")),value)

    def test_rejects_unsafe_or_ambiguous_imports(self):
        original=config_payload({})
        for update in [dict(category="../other"),dict(category="C:/audio"),dict(category=None),dict(cooldown=float("nan")),dict(cooldown=True),dict(enabled="false"),dict(event="execute")]:
            with self.subTest(update=update):
                value=copy.deepcopy(original); value["rules"][0].update(update)
                with self.assertRaises(ValueError): normalize_payload(value)
        duplicate=copy.deepcopy(original); duplicate["rules"][1]=duplicate["rules"][0]
        with self.assertRaises(ValueError): normalize_payload(duplicate)

    def test_custom_categories_and_partial_backward_compatible_defaults(self):
        rule={**default_rules()[0],"category":"点击回应","enabled":False,"cooldown":15}
        value=normalize_payload(dict(format=FORMAT,version=1,rules=[rule]))
        self.assertEqual(value["rules"][0],rule)
        self.assertEqual(len(value["rules"]),26)
