"""Independent or shared resource folders and file-backed dialogue libraries."""
import copy
import json
from pathlib import Path

from .core import writable_path
from .dialogues import normalize_dialogues, starter_dialogues


def load_dialogues(profile):
    value = profile.get("dialogue_file", "")
    if value and Path(value).is_file():
        return normalize_dialogues(json.loads(Path(value).read_text(encoding="utf-8-sig")))
    return normalize_dialogues(copy.deepcopy(profile.get("dialogues", starter_dialogues())))


def write_dialogues(path, entries, protected=()):
    target = writable_path(path, protected)
    entries = normalize_dialogues(entries)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = writable_path(target.with_name(target.name + ".tmp"), protected)
    temp.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def resource_paths(root, protected=()):
    base = writable_path(root, protected)
    return dict(asset_dir=str(base), voice_dir=str(writable_path(base / "voice", protected)),
                bgm_dir=str(writable_path(base / "bgm", protected)), dialogue_file=str(writable_path(base / "dialogues.json", protected)))


def attach_resources(profile, root, protected=()):
    values = resource_paths(root, protected)
    entries = load_dialogues({**profile, **values})
    for key in ["voice_dir", "bgm_dir"]:
        Path(values[key]).mkdir(parents=True, exist_ok=True)
    if not Path(values["dialogue_file"]).exists():
        write_dialogues(values["dialogue_file"], entries, protected)
    return {**profile, **values, "dialogues": entries}
