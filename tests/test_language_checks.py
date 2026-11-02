import unittest
from companion.language_checks import inspect_text,language_issues

class LanguageCheckTests(unittest.TestCase):
    def test_clear_mismatch(self):
        self.assertEqual(inspect_text("こんにちは、今日もよろしくね。","zh"),"mismatch")
        self.assertEqual(inspect_text("你好，今天过得如何？","en"),"mismatch")
        self.assertIsNone(inspect_text("Good morning!","en"))
        self.assertIsNone(inspect_text("こんにちは、今日もよろしくね。","ja"))
    def test_uncertainty_and_custom_code(self):
        self.assertEqual(inspect_text("今日元気","ja"),"uncertain")
        self.assertEqual(inspect_text("hi","ja"),"uncertain")
        self.assertEqual(inspect_text("bonjour","fr"),"unknown")
        self.assertIsNone(inspect_text("123!?","en"))
        self.assertIsNone(inspect_text("你好 hello","auto"))
        self.assertEqual(inspect_text("你好 hello","zh"),"uncertain")
    def test_target_and_reference_are_independent(self):
        settings=dict(text_lang="en",prompt_lang="ja",prompt="こんにちは、今日もよろしくね。")
        self.assertEqual(language_issues(["Good morning!"],settings,"gpt_sovits"),[])
        settings["prompt_lang"]="zh"
        issues=language_issues(["Good morning!"],settings,"gpt_sovits")
        self.assertEqual(len(issues),1);self.assertEqual(issues[0]["field"],"reference")
