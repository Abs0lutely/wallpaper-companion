"""Read-only model discovery and data-only local speech character presets."""
from .i18n import tr
import copy
import os
import re
import uuid
from collections import defaultdict
from pathlib import Path

from .core import AUDIO_EXTENSIONS

CHARACTER_FIELDS = ("project", "python", "gpt_weights", "sovits_weights", "reference", "prompt", "text_lang", "prompt_lang", "speed")
SKIP_DIRS = {"runtime", ".git", ".conda", ".venv", "venv", "__pycache__", "node_modules", "pretrained_models", "tools"}


def normalize_characters(entries):
    if not isinstance(entries, list) or len(entries) > 500:
        raise ValueError(tr('ui.b818d5bf7b7c', '角色预设必须为不超过 500 项的列表'))
    result, identifiers = [], set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("settings"), dict):
            raise ValueError(tr('ui.300e02025eee', '角色预设格式错误'))
        identifier, name = entry.get("id"), entry.get("name")
        if not isinstance(identifier, str) or not 0 < len(identifier) <= 100 or identifier in identifiers:
            raise ValueError(tr('ui.65f09ea37e60', '角色预设 ID 无效或重复'))
        if not isinstance(name, str) or not 0 < len(name.strip()) <= 100:
            raise ValueError(tr('ui.1d2abeb8e9fb', '角色预设名称无效'))
        values = {}
        for key in CHARACTER_FIELDS:
            if key not in entry["settings"]:
                continue
            value = entry["settings"][key]
            if key == "speed":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not .5 <= value <= 2:
                    raise ValueError(tr('ui.381592e961b6', '角色语速需在 0.5–2.0 之间'))
            elif not isinstance(value, str) or len(value) > 64000 or "\x00" in value:
                raise ValueError(tr('ui.34828fa8bc20', '角色字段无效：') + key)
            values[key] = value
        identifiers.add(identifier)
        result.append(dict(id=identifier, name=name.strip(), settings=values))
    return result


def project_file(settings, key):
    value = str(settings.get(key, "")).strip()
    if not value:
        raise ValueError(tr('ui.3dfedd8dd95f', '未填写：') + key)
    path = Path(value).expanduser()
    if not path.is_absolute():
        project = str(settings.get("project", "")).strip()
        if not project:
            raise ValueError(tr('ui.9d6f7ad8571a', '相对路径需要先填写 GPT-SoVITS 项目目录'))
        path = Path(project).expanduser() / path
    return path.resolve()


def version_hint(path):
    match = re.search(r"(?:^|[/_\\-])(v2proplus|v2pro|v[1-4])(?:$|[/_\\-])", str(path), re.I)
    return {"v2pro": "v2Pro", "v2proplus": "v2ProPlus"}.get(match[1].lower(), match[1].lower()) if match else ""


def character_key(stem):
    return re.sub(r"[-_]e(?:poch)?[=_-]?\d+(?:[-_].*)?$", "", stem, flags=re.I).casefold()


def scan_models(project):
    root = Path(project).expanduser().resolve()
    if not root.is_dir() or not (root / "api_v2.py").is_file():
        raise ValueError(tr('ui.de962ab6b581', '请选择包含 api_v2.py 的 GPT-SoVITS 项目目录'))
    models, references, warnings = [], [], []
    def error(exc):
        warnings.append(str(exc))
    for folder, dirs, files in os.walk(root, followlinks=False, onerror=error):
        dirs[:] = [name for name in dirs if name.casefold() not in SKIP_DIRS and not (Path(folder) / name).is_symlink()
                   and (Path(folder) / name).resolve().is_relative_to(root)]
        for name in sorted(files, key=str.casefold):
            file = Path(folder) / name
            if file.is_symlink() or not file.resolve().is_relative_to(root):
                continue
            suffix = file.suffix.lower()
            relative = file.relative_to(root).as_posix()
            if suffix in {".ckpt", ".pth"}:
                models.append(dict(path=relative, kind="gpt" if suffix == ".ckpt" else "sovits",
                    version=version_hint(relative), key=character_key(file.stem), parent=file.parent.relative_to(root).as_posix()))
            elif suffix in AUDIO_EXTENSIONS:
                references.append(relative)
    pairs, used = [], set()
    # Only pair unique names in the same folder, then unique names across weight folders.
    for same_folder in (True, False):
        groups = defaultdict(lambda: dict(gpt=[], sovits=[]))
        for model in models:
            if model["path"] in used:
                continue
            key = (model["version"], model["key"], model["parent"] if same_folder else "")
            groups[key][model["kind"]].append(model)
        for group in groups.values():
            if len(group["gpt"]) == len(group["sovits"]) == 1:
                gpt, sovits = group["gpt"][0], group["sovits"][0]
                parent = Path(gpt["parent"]).name
                name = parent if same_folder and parent not in {"", ".", "models"} and not parent.lower().startswith(("gpt_weights", "sovits_weights", "v1", "v2", "v3", "v4")) else gpt["key"]
                pairs.append(dict(name=name, version=gpt["version"], gpt_weights=gpt["path"], sovits_weights=sovits["path"]))
                used.update((gpt["path"], sovits["path"]))
    unpaired = len(models) - len(used)
    if unpaired:
        warnings.append(tr('ui.f2fab154f35e', '{value0} 个权重无法唯一配对，可在模型下拉框分别选择；未猜选权重。', value0=unpaired))
    return dict(project=str(root), models=sorted(models, key=lambda m: m["path"].casefold()),
                pairs=sorted(pairs, key=lambda p: (p["name"], p["version"], p["gpt_weights"])),
                references=sorted(references, key=str.casefold), warnings=warnings)


def validate_character(settings, require_models=False):
    gpt = str(settings.get("gpt_weights", "")).strip()
    sovits = str(settings.get("sovits_weights", "")).strip()
    if bool(gpt) != bool(sovits) or (require_models and not gpt):
        raise ValueError(tr('ui.7097a5b264ae', '请同时选择配套 GPT (.ckpt) 和 SoVITS (.pth) 模型'))
    paths = []
    for key, suffix in (("gpt_weights", ".ckpt"), ("sovits_weights", ".pth")):
        if settings.get(key):
            path = project_file(settings, key)
            if not path.is_file() or path.suffix.lower() != suffix:
                raise ValueError(tr('ui.618a225f8866', '模型文件不存在或格式不正确：') + key)
            paths.append(path)
    reference = project_file(settings, "reference")
    if not reference.is_file() or reference.suffix.lower() not in AUDIO_EXTENSIONS or not str(settings.get("prompt", "")).strip():
        raise ValueError(tr('ui.917e52b456e1', '请选择参考音频，并填写逐字对应的参考原文'))
    for key in ("text_lang", "prompt_lang"):
        if not str(settings.get(key, "zh")).strip():
            raise ValueError(tr('ui.eee46dc9c2aa', '请填写目标语言及参考语言代码'))
    return paths


def save_character(store, name, settings, identifier=""):
    name = name.strip()
    if not name or len(name) > 100:
        raise ValueError(tr('ui.bc5f0c5b8d2c', '角色名称需为 1–100 个字符'))
    validate_character(settings, require_models=True)
    if settings.get("url"):
        from .services import local_url
        local_url(settings["url"])
    entries = copy.deepcopy(store.config.get("tts_characters", []))
    existing = next((entry for entry in entries if entry["id"] == identifier), None)
    if identifier and existing is None:
        raise ValueError(tr('ui.3fa0e38ecb2a', '角色预设已不存在，请新建'))
    if any(entry["name"].casefold() == name.casefold() and entry["id"] != identifier for entry in entries):
        raise ValueError(tr('ui.ffafa6c8906c', '角色名称已存在，请选中该预设后保存，或使用其他名称'))
    item = dict(id=identifier or uuid.uuid4().hex, name=name,
                settings={key: copy.deepcopy(settings[key]) for key in CHARACTER_FIELDS if key in settings})
    if existing:
        entries[entries.index(existing)] = item
    else:
        entries.append(item)
    entries = normalize_characters(entries)
    previous = store.config
    safe_settings = {key: copy.deepcopy(value) for key, value in settings.items()
                     if key in {*CHARACTER_FIELDS, "url", "python", "allow_external_model_switch"}}
    store.config = {**previous, "tts_characters": entries, "tts_character": item["id"],
                    "tts": safe_settings, "tts_provider": "gpt_sovits",
                    "tts_providers": {**previous.get("tts_providers", {}), "gpt_sovits": safe_settings.copy()}}
    try:
        store.save()
    except Exception:
        store.config = previous
        raise
    return item


def delete_character(store, identifier):
    previous = store.config
    store.config = {**previous, "tts_characters": [item for item in previous.get("tts_characters", []) if item["id"] != identifier],
                    "tts_character": "" if previous.get("tts_character") == identifier else previous.get("tts_character", "")}
    try:
        store.save()
    except Exception:
        store.config = previous
        raise


def reference_transcript(settings):
    reference = project_file(settings, "reference")
    for suffix in (".lab", ".txt"):
        text = reference.with_suffix(suffix)
        if text.is_file():
            if text.stat().st_size > 64_000:
                raise ValueError(tr('ui.5da5c9e09334', '同名参考原文文件过大，请手动核对填写'))
            return text.read_text(encoding="utf-8-sig").strip()
    raise ValueError(tr('ui.f2dc20b8615b', '没有找到与参考音频同名的 .lab 或 .txt；请手动填写逐字原文'))
