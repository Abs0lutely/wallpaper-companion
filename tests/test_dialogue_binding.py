import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from companion.core import Store,new_profile
from companion.dialogue_binding import preview_binding,switch_binding
from companion.file_dialogs import initial_path
from test_core import TEST_TEMP

class BindingTests(unittest.TestCase):
    def test_existing_file_is_loaded_without_rewriting(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            root=Path(tmp);store=Store(root/"config.json");p=new_profile();store.config["profiles"]=[p];store.save()
            file=root/"shared.json";file.write_text('[ {"id":"keep","text":"Existing","category":"A","enabled":true} ]',encoding="utf-8")
            raw=file.read_bytes();_,entries,stamp=preview_binding(store,str(file),p["dialogues"])
            switch_binding(store,p["id"],str(file),p["dialogues"],stamp)
            self.assertEqual(file.read_bytes(),raw);self.assertEqual(store.profile(p["id"])["dialogues"],entries)
            switch_binding(store,p["id"],"",entries,None)
            self.assertEqual(store.profile(p["id"])["dialogue_file"],"");self.assertEqual(file.read_bytes(),raw)
    def test_failure_rolls_back_and_new_file_is_removed(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            root=Path(tmp);store=Store(root/"config.json");p=new_profile();store.config["profiles"]=[p];store.save();before=store.path.read_bytes()
            target=root/"new.json"
            with patch.object(store,"save",side_effect=OSError("No write")):
                with self.assertRaises(OSError):switch_binding(store,p["id"],str(target),p["dialogues"],None)
            self.assertFalse(target.exists());self.assertEqual(store.path.read_bytes(),before)
            self.assertEqual(store.profile(p["id"])["dialogue_file"],"")
    def test_preview_rejects_corrupt_or_changed_files(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            root=Path(tmp);store=Store(root/"config.json");p=new_profile();store.config["profiles"]=[p]
            target=root/"file.json";target.write_text("bad",encoding="utf-8")
            with self.assertRaises(ValueError):preview_binding(store,str(target),p["dialogues"])
            target.write_text("[]",encoding="utf-8");_,_,stamp=preview_binding(store,str(target),[])
            target.write_text("[ ]",encoding="utf-8")
            with self.assertRaises(ValueError):switch_binding(store,p["id"],str(target),[],stamp)
    def test_picker_uses_value_and_nearest_parent(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            root=Path(tmp).resolve();folder=root/"project";folder.mkdir();file=folder/"ref.wav";file.touch()
            self.assertEqual(initial_path(str(file),root,directory=True),str(folder))
            self.assertEqual(initial_path("ref.wav",root,base=folder),str(file))
            self.assertEqual(initial_path(str(folder/"missing/sub"),root),str(folder))
            self.assertEqual(initial_path("",folder),str(folder))
            self.assertEqual(initial_path("",root,base=folder),str(folder))
            self.assertEqual(initial_path("new.json",folder,save=True),str(folder/"new.json"))
