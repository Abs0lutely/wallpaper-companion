import copy
import json
import tempfile
import unittest
from pathlib import Path

from companion.core import Store, new_profile
from companion.dialogues import dialogue_rules, normalize_dialogues, starter_dialogues
from companion.library import scan_wallpapers, apply_bindings, plan_bindings
from companion.services import generate_dialogue_entries
from companion.extensions import SpeechProvider
from test_core import TEST_TEMP, wav_bytes


def project(root, number, title, entry="scene.pkg", kind="scene"):
    folder = root / str(number)
    folder.mkdir(parents=True)
    target = folder / entry
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"fixture")
    (folder / "project.json").write_text(json.dumps(dict(title=title, file=entry, type=kind), ensure_ascii=False), encoding="utf-8-sig")
    return target


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEST_TEMP)
        self.root = Path(self.temp.name)
        self.wallpapers = self.root / "workshop"
        self.engine = self.root / "engine"
        self.wallpapers.mkdir()
        self.engine.mkdir()
        self.store = Store(self.root / "app/config.json")
        self.store.config.update(we_dir=str(self.engine), workshop_dir=str(self.wallpapers))
        project(self.wallpapers, 101, "场景")
        project(self.wallpapers, 102, "视频", "movie.mp4", "video")
        project(self.engine / "projects/myprojects", "local", "网页", "web/index.html", "web")

    def tearDown(self):
        self.temp.cleanup()

    def test_scan_is_readonly_deduplicates_roots_and_skips_broken_projects(self):
        bad = self.wallpapers / "bad"
        bad.mkdir()
        (bad / "project.json").write_text('{"file":"../../outside.mp4"}')
        (self.root / "outside.mp4").write_bytes(b"outside")
        self.store.config["library_roots"] = [str(self.wallpapers)]
        before = {p: p.read_bytes() for p in self.wallpapers.rglob("*") if p.is_file()}
        result = scan_wallpapers(self.store.config)
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(before, {p: p.read_bytes() for p in self.wallpapers.rglob("*") if p.is_file()})
        self.assertEqual({r["type"] for r in result["records"]}, {"scene", "video", "web"})

    def test_bulk_shared_binding_is_idempotent_and_updates_folders_only(self):
        records = scan_wallpapers(self.store.config)["records"]
        voice, bgm, replacement = [self.root / p for p in ["voice", "bgm", "other"]]
        for path in [voice, bgm, replacement]:
            path.mkdir()
        result = apply_bindings(self.store, records, mode="shared", voice_dir=str(voice), bgm_dir=str(bgm))
        self.assertEqual(result, dict(created=3, updated=0, skipped=0))
        before = copy.deepcopy(self.store.config["profiles"])
        result = apply_bindings(self.store, records, mode="shared", voice_dir=str(replacement))
        self.assertEqual(result["skipped"], 3)
        self.assertEqual(before, self.store.config["profiles"])
        result = apply_bindings(self.store, records[:1], mode="shared", voice_dir=str(replacement), update_existing=True)
        self.assertEqual(result["updated"], 1)
        edited = self.store.bound_profile(records[0]["path"])
        prior = next(p for p in before if p["id"] == edited["id"])
        self.assertEqual(edited["rules"], prior["rules"])
        self.assertEqual(edited["name"], prior["name"])
        self.assertEqual(edited["voice_dir"], str(replacement.resolve()))
        self.assertEqual(len(Store(self.store.path).config["profiles"]), 3)

    def test_published_scene_json_entry_resolves_existing_package(self):
        metadata = self.wallpapers / "101/project.json"
        metadata.write_text(json.dumps(dict(title="已打包场景", file="scene.json", type="Scene")), encoding="utf-8")
        result = scan_wallpapers(self.store.config)
        record = next(r for r in result["records"] if r["title"] == "已打包场景")
        self.assertEqual(Path(record["path"]).name, "scene.pkg")
        self.assertEqual(result["warnings"], [])

    def test_separate_bindings_clone_template_and_protect_library(self):
        template = new_profile("模板")
        template["rules"][0]["hotkey"] = "<f9>"
        self.store.config["profiles"].append(template)
        records = scan_wallpapers(self.store.config)["records"]
        apply_bindings(self.store, records, mode="separate", template_id=template["id"])
        profiles = [p for p in self.store.config["profiles"] if p["wallpaper"]]
        self.assertEqual(len({p["voice_dir"] for p in profiles}), 3)
        for profile in profiles:
            self.assertTrue(Path(profile["voice_dir"]).is_dir())
            self.assertEqual(profile["rules"][0]["hotkey"], "<f9>")
            self.assertNotEqual(profile["rules"][0]["id"], template["rules"][0]["id"])
        with self.assertRaises(ValueError):
            plan_bindings(self.store.config, records, mode="separate", data_root=self.wallpapers, update_existing=True)

    def test_missing_entry_aborts_without_partial_config_changes(self):
        records = scan_wallpapers(self.store.config)["records"]
        Path(records[-1]["path"]).unlink()
        before = copy.deepcopy(self.store.config)
        with self.assertRaises(ValueError):
            apply_bindings(self.store, records, mode="separate")
        self.assertEqual(self.store.config, before)


class DialogueTests(unittest.TestCase):
    def test_starter_library_categories_and_validation(self):
        entries = starter_dialogues()
        self.assertEqual(len(entries), 38)
        self.assertEqual(len({e["id"] for e in entries}), 38)
        self.assertEqual(len({e["category"] for e in entries}), 6)
        self.assertEqual(normalize_dialogues(entries), entries)
        entries[0]["text"] = "自己填写的新台词"
        self.assertNotEqual(entries[0], starter_dialogues()[0])
        for category in ["../bad", "..", "bad/name", "bad\\name", "", "CON", "bad\x00name", "bad."]:
            with self.assertRaises(ValueError):
                normalize_dialogues([dict(text="测试", category=category)])
        self.assertEqual(len(dialogue_rules()), 6)

    def test_categorized_generation_skips_existing_and_preserves_disabled_lines(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
            calls = []
            provider = SpeechProvider("fixture", "Fixture", [], lambda settings, text: (calls.append(text) or wav_bytes()), lambda settings: "ok")
            entries = [dict(text="早安", category="早晨", enabled=True), dict(text="不生成", category="夜间", enabled=False)]
            result = generate_dialogue_entries({}, entries, temp, provider=provider)
            self.assertEqual(len(result["paths"]), 1)
            self.assertEqual(Path(result["paths"][0]).relative_to(temp).as_posix(), "早晨/早安.wav")
            result = generate_dialogue_entries({}, entries, temp, provider=provider)
            self.assertEqual(result, dict(paths=[], skipped=1))
            self.assertEqual(calls, ["早安"])
            result = generate_dialogue_entries({}, entries, temp, provider=provider, skip_existing=False)
            self.assertEqual(Path(result["paths"][0]).name, "早安 (2).wav")
            with self.assertRaises(ValueError):
                generate_dialogue_entries({}, [dict(text="不能生成", category="../outside")], temp, provider=provider)
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
