"""Portable, data-only interaction presets. Never import local paths, keys or plugins."""
import copy
import json
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

from .core import Store, new_profile, new_rule, writable_path
from .dialogues import normalize_dialogues
from .rules import BUILTIN_EVENTS, validate_rule

FORMAT = "wallpaper-companion-preset"
VERSION = 1
NUMERIC = {"voice_volume": (0, 100), "bgm_volume": (0, 100), "duck_percent": (0, 100), "global_cooldown": (0, 3600)}
BOOLEAN = {"enabled", "desktop_only", "fullscreen_mute", "bgm_enabled", "bgm_shuffle"}
RULE_FIELDS = {"name", "enabled", "event", "hotkey", "source", "keyword", "start", "end", "at", "cooldown", "interval_min", "interval_max"}


def relative_source(value):
    if not isinstance(value, str) or len(value) > 1000 or "\x00" in value:
        raise ValueError("音频来源不是有效文本")
    source = value.replace("\\", "/")
    if PureWindowsPath(value).is_absolute() or PureWindowsPath(value).drive or PurePosixPath(source).is_absolute() or ":" in source or ".." in PurePosixPath(source).parts:
        raise ValueError("共享配置只能使用语音目录内的相对来源，不能包含绝对路径或上级目录")
    return "" if source == "." else source


def export_payload(profiles):
    result, warnings = [], []
    for profile in profiles:
        rules = []
        for original in profile.get("rules", []):
            rule = {key: copy.deepcopy(value) for key, value in original.items() if key in RULE_FIELDS}
            source = rule.get("source", "")
            if Path(source).is_absolute() or PureWindowsPath(source).is_absolute():
                try:
                    if not profile.get("voice_dir"):
                        raise ValueError("no voice root")
                    source = str(Path(source).resolve().relative_to(Path(profile["voice_dir"]).resolve()))
                except ValueError:
                    source = PureWindowsPath(source).name
                    warnings.append(profile["name"] + "：某条规则引用外部文件，已仅保留其名称，请在接收电脑核对来源。")
            rule["source"] = relative_source(source)
            rules.append(rule)
        result.append(dict(name=profile["name"], settings={key: profile[key] for key in NUMERIC.keys() | BOOLEAN if key in profile},
                           rules=rules, dialogues=normalize_dialogues(profile.get("dialogues", []))))
    payload = dict(format=FORMAT, version=VERSION, profiles=result)
    validate_payload(payload)
    return payload, warnings


def validate_payload(payload, available_events=None):
    if not isinstance(payload, dict) or payload.get("format") != FORMAT or type(payload.get("version")) is not int or payload["version"] != VERSION:
        raise ValueError("不支持的配置文件格式或版本")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 200:
        raise ValueError("配置文件需包含 1–200 个配置")
    cleaned, warnings = [], []
    for profile in profiles:
        if not isinstance(profile, dict) or not isinstance(profile.get("name"), str) or not 1 <= len(profile["name"].strip()) <= 100:
            raise ValueError("配置名称无效")
        settings = profile.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError("播放设置结构无效")
        safe_settings = {}
        for key, limits in NUMERIC.items():
            if key in settings:
                if type(settings[key]) is not int or not limits[0] <= settings[key] <= limits[1]:
                    raise ValueError("播放设置数值不合法：" + key)
                safe_settings[key] = settings[key]
        for key in BOOLEAN:
            if key in settings:
                if type(settings[key]) is not bool:
                    raise ValueError("开关设置必须是布尔值：" + key)
                safe_settings[key] = settings[key]
        entries = profile.get("dialogues", [])
        rules = profile.get("rules", [])
        if not isinstance(entries, list) or len(entries) > 5000 or not isinstance(rules, list) or len(rules) > 500:
            raise ValueError("台词或规则数量超出限制")
        safe_rules = []
        for original in rules:
            if not isinstance(original, dict):
                raise ValueError("规则结构无效")
            rule = new_rule()
            rule.update({key: copy.deepcopy(value) for key, value in original.items() if key in RULE_FIELDS})
            rule["source"] = relative_source(rule.get("source", ""))
            if type(rule.get("enabled")) is not bool or not isinstance(rule.get("keyword"), str) or len(rule["keyword"]) > 500:
                raise ValueError("规则开关或筛选文字不合法")
            validate_rule(rule)
            if available_events is not None and rule["event"] not in available_events:
                rule["enabled"] = False
                warnings.append("事件扩展不可用，已禁用规则：" + rule["name"])
            safe_rules.append(rule)
        cleaned.append(dict(name=profile["name"].strip(), settings=safe_settings, rules=safe_rules, dialogues=normalize_dialogues(entries)))
    return cleaned, warnings


def read_preset(path):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("配置文件不能超过 2 MiB")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_payload(payload)
    return payload


def write_preset(path, profiles, protected=()):
    target = writable_path(path, protected)
    payload, warnings = export_payload(profiles)
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(data.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("导出的配置超过 2 MiB，请减少一次选择的配置数量")
    target.write_text(data, encoding="utf-8")
    return warnings


def import_payload(store, payload, target_id=None, available_events=BUILTIN_EVENTS):
    profiles, warnings = validate_payload(payload, available_events)
    if target_id and len(profiles) != 1:
        raise ValueError("应用到现有配置时文件只能包含一个配置")
    updated = copy.deepcopy(store.config)
    created = []
    directories = []
    for imported in profiles:
        if target_id:
            profile = next((p for p in updated["profiles"] if p["id"] == target_id), None)
            if profile is None:
                raise ValueError("目标配置不存在")
            # Detach shared text instead of unexpectedly changing other wallpapers.
            profile.update(dialogue_file="", asset_dir="")
        else:
            profile = new_profile(imported["name"])
            base = store.path.parent / "audio" / profile["id"]
            for name in ["voice", "bgm"]:
                directories.append(writable_path(base / name, store.protected()))
            profile.update(voice_dir=str(base / "voice"), bgm_dir=str(base / "bgm"))
            updated["profiles"].append(profile)
        profile.update(imported["settings"], rules=imported["rules"], dialogues=imported["dialogues"])
        # Do not transfer a sender's claim that a different wallpaper is muted.
        profile.update(original_audio_override="auto", original_audio_policy="safe")
        created.append(profile["id"])
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)
    previous = store.config
    store.config = updated
    try:
        store.save()
    except Exception:
        store.config = previous
        raise
    return dict(profile_ids=created, warnings=warnings)
