from __future__ import annotations

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


def writable_path(path: str | Path, extra_protected=()) -> Path:
    target = Path(path).expanduser().resolve()
    for root in [*protected_directories(), *extra_protected]:
        root = Path(root).resolve()
        if target == root or root in target.parents:
            raise ValueError("此目录只读：请选择 Wallpaper Engine 和工坊目录之外的位置。")
    return target


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
            raise ValueError("时间格式错误")
        return h * 60 + m
    a, b = value(start), value(end)
    return a == b or (a <= minute < b if a < b else minute >= a or minute < b)


def audio_files(folder: str, recursive=True) -> list[Path]:
    if not folder:
        return []
    root = Path(folder).expanduser()
    if not root.is_dir():
        return []
    try:
        return sorted((p for p in (root.rglob("*") if recursive else root.iterdir())
                       if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS), key=lambda p: str(p).casefold())
    except OSError:
        return []


def candidates(profile: dict, rule: dict) -> list[Path]:
    source = rule.get("source", "").strip() or profile.get("voice_dir", "")
    if source and not Path(source).is_absolute():
        base = profile.get("voice_dir", "")
        if not base:
            return []
        source = str(Path(base) / source)
    if source and Path(source).is_file():
        files = [Path(source)] if Path(source).suffix.lower() in AUDIO_EXTENSIONS else []
    else:
        files = audio_files(source)
    keyword = rule.get("keyword", "").strip().casefold()
    return [p for p in files if not keyword or keyword in p.stem.casefold()]


def new_rule(event="key", name="快捷键回应") -> dict:
    return dict(id=uuid.uuid4().hex, name=name, enabled=True, event=event,
                hotkey="<f8>", source="", keyword="", start="00:00", end="00:00",
                cooldown=20, interval_min=300, interval_max=600)


def new_profile(name="新的壁纸配置", wallpaper="") -> dict:
    from .dialogues import starter_dialogues
    return dict(id=uuid.uuid4().hex, name=name, wallpaper=wallpaper, voice_dir="", bgm_dir="",
                asset_dir="", dialogue_file="", original_audio_policy="safe", original_audio_override="auto", bgm_paused=False,
                enabled=True, desktop_only=True, fullscreen_mute=True, bgm_enabled=True,
                bgm_shuffle=True, voice_volume=80, bgm_volume=25, duck_percent=25,
                global_cooldown=8, dialogues=starter_dialogues(), rules=[new_rule(), new_rule("random", "随机陪伴 · 每 5–10 分钟")])


def defaults() -> dict:
    we_dir, workshop_dir = discover_wallpaper_engine()
    return dict(version=4, we_dir=we_dir, workshop_dir=workshop_dir, library_roots=[], library_backend="wallpaper_engine", ffprobe="",
                monitor=0, poll_seconds=4, manual_profile="", profiles=[], hover_help=True,
                wallpaper_backend="wallpaper_engine", audio_backend="qt", input_backend="pynput",
                enabled_plugins=[], tts_provider="gpt_sovits", tts_providers={}, audio_detector="builtin",
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
                    raise ValueError("配置结构错误")
                self.config.update(saved)
                self.config["tts"] = {**defaults()["tts"], **saved.get("tts", {})}
                if "gpt_sovits" not in self.config["tts_providers"]:
                    self.config["tts_providers"]["gpt_sovits"] = self.config["tts"].copy()
                from .dialogues import starter_dialogues
                for profile in self.config["profiles"]:
                    profile.setdefault("dialogues", starter_dialogues())
                    for key, value in dict(asset_dir="", dialogue_file="", original_audio_policy="safe", original_audio_override="auto", bgm_paused=False).items():
                        profile.setdefault(key, value)
            except (ValueError, OSError) as exc:
                raise ValueError(f"无法读取配置 {self.path}：{exc}。原文件已保留。") from exc

    def save(self):
        path = writable_path(self.path, self.protected())
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def protected(self):
        return [p for p in [self.config.get("we_dir"), self.config.get("workshop_dir"), *self.config.get("library_roots", [])] if p]

    def profile(self, profile_id):
        return next((p for p in self.config["profiles"] if p["id"] == profile_id), None)

    def bound_profile(self, wallpaper):
        key = identity(wallpaper)
        return next((p for p in self.config["profiles"] if key and identity(p["wallpaper"]) == key), None)


class RuleEngine:
    """Pure scheduling logic; no audio or hooks on the listener thread."""
    def __init__(self, rng=None):
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
            files = candidates(profile, rule)
            if not files:
                continue
            self.last[rule["id"]] = now
            self.last_global = now
            if event == "scheduled":
                self.daily_fired[rule["id"]] = clock.date()
            return rule, self.rng.choice(files)
        return None


def filename_for(text: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text.strip()).rstrip(" .")
    if not name:
        raise ValueError("台词不能为空")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "_" + name
    if len(name) > 70:
        name = name[:58] + "_" + hashlib.sha256(text.encode()).hexdigest()[:8]
    return name + ".wav"


def save_generated(folder, text, data, protected=()):
    import io
    import wave
    with wave.open(io.BytesIO(data), "rb") as wav:
        if wav.getnframes() <= 0:
            raise ValueError("接口返回了空 WAV")
    directory = writable_path(folder, protected)
    directory.mkdir(parents=True, exist_ok=True)
    filename = filename_for(text)
    base = Path(filename).stem
    for index in range(10000):
        target = writable_path(directory / (filename if index == 0 else f"{base} ({index + 1}).wav"), protected)
        try:
            with target.open("xb") as out:
                out.write(data)
            return target
        except FileExistsError:
            continue
    raise ValueError("同名文件过多")
