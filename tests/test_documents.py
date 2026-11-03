import tempfile
import unittest
from pathlib import Path
from companion.i18n import set_language
from companion.documents_ui import document_path, reading_markdown
from test_core import TEST_TEMP


class DocumentTests(unittest.TestCase):
    def tearDown(self):
        set_language("zh-CN")

    def test_paths_choose_active_language_and_keep_specialized_documents(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            root=Path(tmp).resolve()
            for locale,suffix in (("en-US",".en.md"),("zh-CN",".md")):
                set_language(locale)
                for name in ("USER_GUIDE.md","USER_GUIDE.en.md"):
                    self.assertEqual(document_path(root,root/name),root/("USER_GUIDE"+suffix))
                for name in ("README.md","README.en.md","USAGE.md","USAGE.en.md"):
                    self.assertEqual(document_path(root,root/name),root/("USAGE"+suffix))
                self.assertEqual(document_path(root,root/"BUILDING.md"),root/"BUILDING.md")
                with self.assertRaises(ValueError): document_path(root,root/"../outside.md")
                with self.assertRaises(ValueError): document_path(root,root/"script.py")

    def test_reference_tables_become_readable_fields(self):
        source="# Guide\n\n| Field | Purpose | When |\n|---|---|---|\n| Volume | Adjust voice | Save |\n\n[Next](USAGE.md)"
        result=reading_markdown(source)
        self.assertIn("**Volume**",result)
        self.assertIn("**Purpose:** Adjust voice",result)
        self.assertIn("**When:** Save",result)
        self.assertIn("[Next](USAGE.md)",result)
        self.assertNotIn("|---",result)

    def test_both_languages_ship_reading_documents(self):
        root=Path(__file__).resolve().parents[1]
        for name in ("USAGE.md","USAGE.en.md","USER_GUIDE.md","USER_GUIDE.en.md"):
            text=(root/name).read_text(encoding="utf-8-sig")
            self.assertGreater(len(text),1000,name)
            self.assertNotIn("<img",text)
            self.assertNotIn("![",text)
            for script in ("scripts/build_windows.py","scripts/package_source.py","companion/program_update.py"):
                self.assertIn('"'+name+'"',(root/script).read_text(encoding="utf-8"))
