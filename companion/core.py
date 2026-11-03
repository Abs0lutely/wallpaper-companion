from __future__ import annotations
from .i18n import tr

import copy
import hashlib
import json
import os
import random
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from .paths import discover_wallpaper_engine, protected_directories
from .runtime import LAYOUT

ROOT = LAYOUT.app_dir
DATA = LAYOUT.data_dir
PLUGIN_DIR = LAYOUT.plugin_dir
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus"}


from .paths import writable_path

def identity(path: str) -> str:
    if not path.strip():
        return ""
    return os.path.normcase(os.path.normpath(path.strip().strip('"')))


def time_matches(start: str, end: str, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    minute = now.hour * 60 + now.minute
    def value(s):
        h, m = map(int, s.split(":"))
        if not 0 <= h <= 23 or not 0 <= m <= 59:
            raise ValueError(tr('ui.ffec3cf79cfa', '时间格式错误'))
        return h * 60 + m
    a, b = value(start), value(end)
    return a == b or (a <= minute < b if a < b else minute >= a or minute < b)


def audio_files(folder: str, recursive=True) -> list[Path]:
    if not folder:
        return []
    root = Path(folder).expanduser()
    if not root.is_dir():
        return []
    files = []
    pending = [root]
    try:
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    if recursive and entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif Path(entry.name).suffix.lower() in AUDIO_EXTENSIONS and entry.is_file():
                        files.append(Path(entry.path))
        return sorted(files, key=lambda path: str(path).casefold())
    except OSError:
        return []



def candidates(profile: dict, rule: dict, scan=None) -> list[Path]:
    scan = scan or audio_files
    source = rule.get("source", "").strip() or profile.get("voice_dir", "")
    if source and not Path(source).is_absolute():
        base = profile.get("voice_dir", "")
        if not base and not profile.get("use_bundled_demo",False):
            return []
        source = str(Path(base) / source) if base else ""
    if source and Path(source).is_file():
        files = [Path(source)] if Path(source).suffix.lower() in AUDIO_EXTENSIONS else []
    else:
        files = scan(source)
    if not rule.get("source", "").strip():
        from .action_lines import EVENT_LINES
        from .voice_locales import category_for, LOCALES
        operation_categories = {category_for(category,locale) for category, _ in EVENT_LINES.values() for locale in LOCALES}
        root = Path(source).expanduser() if source else None
        files = [p for p in files if root is None or not p.relative_to(root).parts or p.relative_to(root).parts[0] not in operation_categories]
    if not files and rule.get("source", ""):
        from .voice_locales import legacy_candidates
        files=legacy_candidates(profile.get("voice_dir", ""), rule["source"], scan=scan)
    if not files and profile.get("use_bundled_demo", False) and not scan(profile.get("voice_dir", "")):
        from .bundled_audio import bundled_root
        relative = rule.get("source", "").strip()
        if not relative or not Path(relative).is_absolute() and ".." not in Path(relative).parts and ":" not in relative:
            locale=profile.get("demo_language", "zh-CN")
            if relative.endswith("·ja-JP"):locale="ja-JP"
            if locale=="ja-JP":
                from .dialogues import CATEGORIES
                if relative in CATEGORIES:relative += "·ja-JP"
            fallback = bundled_root()/("starter-voice-ja-JP" if locale=="ja-JP" else "starter-voice")/relative
            files = [fallback] if fallback.is_file() and fallback.suffix.lower() in AUDIO_EXTENSIONS else scan(str(fallback))
    keyword = rule.get("keyword", "").strip().casefold()
    return [p for p in files if not keyword or keyword in p.stem.casefold()]


def new_rule(event="key", name=None) -> dict:
    if name is None:
        name = tr('ui.71dd8335a7de', '快捷键回应')
    return dict(id=uuid.uuid4().hex, name=name, enabled=True, event=event,
                hotkey="<f8>", source="", keyword="", start="00:00", end="00:00",
                cooldown=20, interval_min=300, interval_max=600)


def new_profile(name=None, wallpaper="") -> dict:
    if name is None:
        name = tr('ui.49a7b7657842', '新的壁纸配置')
    from .dialogues import starter_dialogues
    return dict(id=uuid.uuid4().hex, name=name, wallpaper=wallpaper, voice_dir="", bgm_dir="",
                asset_dir="", private_asset_dir="", dialogue_file="", original_audio_policy="safe", original_audio_override="auto", bgm_paused=False, use_bundled_demo=True, demo_language="zh-CN",
                enabled=True, desktop_only=True, fullscreen_mute=True, bgm_enabled=True,
                bgm_shuffle=True, voice_volume=80, bgm_volume=25, duck_percent=25,
                global_cooldown=8, dialogues=starter_dialogues(), rules=[new_rule(), new_rule("random", tr('ui.cdd7f524c681', '随机陪伴 · 每 5–10 分钟'))])


def defaults() -> dict:
    from .operation_rules import default_rules
    we_dir, workshop_dir = discover_wallpaper_engine()
    return dict(version=4, run_mode="wallpaper_engine", standalone_profile="", ui_language="zh-CN", auto_update_enabled=True, we_dir=we_dir, workshop_dir=workshop_dir, library_roots=[], library_backend="wallpaper_engine", ffprobe="",
                monitor=0, poll_seconds=4, manual_profile="", profiles=[], hover_help=True, shared_asset_dir="",
                operation_voice_enabled=True, operation_voice_dir="", operation_voice_pack_only=False,
                operation_voice_rules=default_rules(), operation_voice_min_interval=1.2, tts_filename_model="",
                appearance=dict(background="", accent="#edb2c4", auto_color=True),
                wallpaper_backend="wallpaper_engine", audio_backend="qt", input_backend="pynput",
                enabled_plugins=[], tts_provider="gpt_sovits", tts_providers={}, tts_characters=[], tts_character="", audio_detector="builtin",
                tts=dict(url="http://127.0.0.1:9880", project=os.environ.get("GPT_SOVITS_DIR", ""),
                         reference="", prompt="", text_lang="zh", prompt_lang="zh", speed=1.0))


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or DATA / "config.json"
        self.config = defaults()
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(saved, dict) or not isinstance(saved.get("profiles", []), list):
                    raise ValueError(tr('ui.f84bdfec490a', '配置结构错误'))
                self.config.update(saved)
                if not isinstance(self.config.get("run_mode"),str) or self.config.get("run_mode") not in {"wallpaper_engine","standalone"}:self.config["run_mode"]="wallpaper_engine"
                if not isinstance(self.config.get("standalone_profile"),str):self.config["standalone_profile"]=""
                from .i18n import normalize_language
                self.config["ui_language"] = normalize_language(self.config.get("ui_language"))
                if not isinstance(self.config.get("auto_update_enabled"), bool):
                    self.config["auto_update_enabled"] = True
                if not isinstance(self.config["operation_voice_enabled"], bool) or not isinstance(self.config["operation_voice_dir"], str):
                    raise ValueError(tr('ui.0ef515b8ebcc', '操作语音开关必须是布尔值，目录必须是文本'))
                if not isinstance(self.config["tts_filename_model"],str) or len(self.config["tts_filename_model"])>200:
                    raise ValueError(tr('ui.5bdc03ca325c', '音频文件模型标签必须是200字以内的文本'))
                if not isinstance(self.config["operation_voice_pack_only"],bool):raise ValueError(tr('ui.f84bdfec490a', '配置结构错误'))
                from .operation_rules import config_payload
                self.config["operation_voice_rules"] = config_payload(self.config)["rules"]
                self.config["operation_voice_min_interval"] = config_payload(self.config)["min_interval"]
                from .characters import normalize_characters
                self.config["tts_characters"] = normalize_characters(self.config["tts_characters"])
                from .appearance import normalize_appearance
                self.config["appearance"] = normalize_appearance(self.config.get("appearance"))
                self.config["tts"] = {**defaults()["tts"], **saved.get("tts", {})}
                if "gpt_sovits" not in self.config["tts_providers"]:
                    self.config["tts_providers"]["gpt_sovits"] = self.config["tts"].copy()
                from .dialogues import starter_dialogues
                for profile in self.config["profiles"]:
                    profile.setdefault("dialogues", starter_dialogues())
                    if not isinstance(profile.get("demo_language"),str) or profile.get("demo_language") not in {"zh-CN", "ja-JP"}:profile["demo_language"]="zh-CN"
                    for key, value in dict(asset_dir="", private_asset_dir="", dialogue_file="", original_audio_policy="safe", original_audio_override="auto", bgm_paused=False, use_bundled_demo=False).items():
                        profile.setdefault(key, value)
                    if not isinstance(profile["use_bundled_demo"],bool):
                        raise ValueError(tr('ui.d01e015b2dda', '随附示例语音开关必须是布尔值'))
            except (ValueError, OSError) as exc:
                raise ValueError(tr('ui.2a367740d9fc', '无法读取配置 {value0}：{value1}。原文件已保留。', value0=self.path, value1=exc)) from exc

    def save(self):
        path = writable_path(self.path, self.protected())
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def protected(self):
        from .bundled_audio import bundled_root
        return [p for p in [self.config.get("we_dir"), self.config.get("workshop_dir"), *self.config.get("library_roots", []), str(bundled_root())] if p]

    def profile(self, profile_id):
        return next((p for p in self.config["profiles"] if p["id"] == profile_id), None)

    def bound_profile(self, wallpaper):
        key = identity(wallpaper)
        return next((p for p in self.config["profiles"] if key and identity(p["wallpaper"]) == key), None)


class RuleEngine:
    """Pure scheduling logic; no audio or hooks on the listener thread."""
    def __init__(self, rng=None, scan=None):
        self.scan = scan
        self.rng = rng or random.Random()
        self.daily_fired = {}
        self.reset()

    def reset(self):
        self.last = {}
        self.next_due = {}
        self.last_global = float("-inf")

    def schedule(self, rule, now):
        low = max(5, int(rule.get("interval_min", 300)))
        high = max(low, int(rule.get("interval_max", 600)))
        self.next_due[rule["id"]] = now + self.rng.uniform(low, high)

    def eligible(self, profile, rule, now, clock):
        return (profile.get("enabled", True) and rule.get("enabled", True)
                and time_matches(rule.get("start", "00:00"), rule.get("end", "00:00"), clock)
                and now - self.last_global >= profile.get("global_cooldown", 8)
                and now - self.last.get(rule["id"], float("-inf")) >= rule.get("cooldown", 20))

    def choose(self, profile, event, now=None, clock=None, hotkey=""):
        now = time.monotonic() if now is None else now
        clock = clock or datetime.now()
        for rule in profile.get("rules", []):
            if rule.get("event") != event:
                continue
            if event == "key" and rule.get("id") != hotkey:
                continue
            if event == "scheduled":
                if clock.strftime("%H:%M") != rule.get("at", "09:00") or self.daily_fired.get(rule["id"]) == clock.date():
                    continue
            if event == "random":
                if rule["id"] not in self.next_due:
                    self.schedule(rule, now)
                if now < self.next_due[rule["id"]]:
                    continue
                # Reschedule even when inactive/outside the window, avoiding busy retries.
                self.schedule(rule, now)
            if not self.eligible(profile, rule, now, clock):
                continue
            files = candidates(profile, rule, self.scan)
            if not files:
                continue
            self.last[rule["id"]] = now
            self.last_global = now
            if event == "scheduled":
                self.daily_fired[rule["id"]] = clock.date()
            return rule, self.rng.choice(files)
        return None


def filename_for(text: str, model_name: str | None = None) -> str:
    if model_name:
        tag = Path(filename_for(model_name)).stem
        if len(tag) > 24:
            tag = tag[:15] + "_" + hashlib.sha256(model_name.encode()).hexdigest()[:8]
        name = Path(filename_for(text)).stem
        available = 70 - len(tag) - 1
        if len(name) > available:
            name = name[:available-9] + "_" + hashlib.sha256(text.encode()).hexdigest()[:8]
        return name + "-" + tag + ".wav"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text.strip()).rstrip(" .")
    if not name:
        raise ValueError(tr('ui.475fe78a224f', '台词不能为空'))
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "_" + name
    if len(name) > 70:
        name = name[:58] + "_" + hashlib.sha256(text.encode()).hexdigest()[:8]
    return name + ".wav"


def save_generated(folder, text, data, protected=(), model_name=None):
    import io
    import wave
    with wave.open(io.BytesIO(data), "rb") as wav:
        if wav.getnframes() <= 0:
            raise ValueError(tr('ui.7e9a1a0a3c8e', '接口返回了空 WAV'))
    directory = writable_path(folder, protected)
    directory.mkdir(parents=True, exist_ok=True)
    filename = filename_for(text, model_name)
    base = Path(filename).stem
    for index in range(10000):
        target = writable_path(directory / (filename if index == 0 else f"{base} ({index + 1}).wav"), protected)
        try:
            with target.open("xb") as out:
                out.write(data)
            return target
        except FileExistsError:
            continue
    raise ValueError(tr('ui.5f4379c8c63b', '同名文件过多'))
