"""Independent or shared resource folders and file-backed dialogue libraries."""
import copy
import json
from pathlib import Path

from .core import writable_path
from .dialogues import normalize_dialogues, starter_dialogues


def shared_root(store):
    from .runtime import LAYOUT
    default = LAYOUT.shared_dir if store.path.resolve() == (LAYOUT.data_dir / "config.json").resolve() else store.path.parent / "shared"
    return Path(store.config.get("shared_asset_dir") or default).expanduser().resolve()


def private_root(store, profile):
    return Path(profile.get("private_asset_dir") or store.path.parent / "audio" / profile["id"]).expanduser().resolve()


def channel_resources(profile, shared, private, modes, protected=()):
    """Reference shared folders directly, or create private folders; never move audio."""
    shared_values = resource_paths(shared, protected)
    private_values = resource_paths(private, protected)
    result = copy.deepcopy(profile)
    for key in ("voice_dir", "bgm_dir", "dialogue_file"):
        mode = modes.get(key, "custom")
        if mode not in {"shared", "private", "custom"}:
            raise ValueError("未知资源目录模式")
        value = shared_values[key] if mode == "shared" else private_values[key] if mode == "private" else profile.get(key, "")
        if not value:
            raise ValueError("自定义目录为空，请选择共享或专用模式")
        result[key] = str(writable_path(value, protected))
    result["asset_dir"] = private_values["asset_dir"]
    result["private_asset_dir"] = private_values["asset_dir"]
    entries = load_dialogues(result)
    for key in ("voice_dir", "bgm_dir"):
        Path(result[key]).mkdir(parents=True, exist_ok=True)
    if not Path(result["dialogue_file"]).exists():
        write_dialogues(result["dialogue_file"], entries, protected)
    result["dialogues"] = entries
    return result


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
