import json,tempfile,unittest
from pathlib import Path
from companion.core import Store,new_profile
from companion.library import remove_profiles
from test_core import TEST_TEMP

class ModeTests(unittest.TestCase):
    def test_legacy_and_invalid_modes(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            path=Path(tmp)/"config.json"
            for mode in ([],None,"unknown"):
                path.write_text(json.dumps(dict(run_mode=mode,standalone_profile=[],profiles=[])),encoding="utf-8")
                config=Store(path).config
                self.assertEqual(config["run_mode"],"wallpaper_engine")
                self.assertEqual(config["standalone_profile"],"")
    def test_independent_choices_persist_and_deleted_reference_clears(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            store=Store(Path(tmp)/"config.json");we=new_profile("WE","wallpaper.pkg");sound=new_profile("Sound")
            store.config.update(profiles=[we,sound],manual_profile=we["id"],standalone_profile=sound["id"],run_mode="standalone")
            store.save();store=Store(store.path)
            self.assertEqual(store.config["manual_profile"],we["id"])
            self.assertEqual(store.config["standalone_profile"],sound["id"])
            remove_profiles(store,[sound["id"]])
            self.assertEqual(store.config["standalone_profile"],"")
            self.assertEqual(store.config["manual_profile"],we["id"])
