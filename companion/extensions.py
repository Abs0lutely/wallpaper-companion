"""Versioned capability registry; external Python extensions are explicitly enabled."""
from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

API_VERSION = 1


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"  # text/password/file/directory/multiline/float/bool; builtin gpt_model/sovits_model
    default: Any = ""
    help: str = ""


@dataclass
class SpeechProvider:
    id: str
    title: str
    fields: list[Field]
    synthesize: Callable[[dict, str], bytes]  # return a complete PCM WAV
    check: Callable[[dict], str]
    description: str = ""
    start: Callable | None = None


@dataclass
class Registry:
    speech: dict[str, SpeechProvider] = field(default_factory=dict)
    wallpapers: dict[str, tuple[str, Callable]] = field(default_factory=dict)
    audio: dict[str, tuple[str, Callable]] = field(default_factory=dict)
    inputs: dict[str, tuple[str, Callable]] = field(default_factory=dict)
    events: dict[str, tuple[str, Callable | None]] = field(default_factory=dict)
    libraries: dict[str, tuple[str, Callable]] = field(default_factory=dict)
    audio_detectors: dict[str, tuple[str, Callable]] = field(default_factory=dict)
    loaded: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def register_speech(self, provider):
        self._unique(self.speech, provider.id)
        self.speech[provider.id] = provider

    @staticmethod
    def _unique(mapping, identifier):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", identifier) or identifier in mapping:
            raise ValueError("扩展 ID 无效或重复：" + identifier)

    def _register(self, mapping, identifier, title, implementation):
        self._unique(mapping, identifier)
        mapping[identifier] = (title, implementation)

    def register_wallpaper(self, identifier, title, query):
        self._register(self.wallpapers, identifier, title, query)

    def register_audio(self, identifier, title, factory):
        self._register(self.audio, identifier, title, factory)

    def register_input(self, identifier, title, factory):
        self._register(self.inputs, identifier, title, factory)

    def register_event(self, identifier, title, poll=None):
        self._register(self.events, identifier, title, poll)

    def register_library(self, identifier, title, scan):
        self._register(self.libraries, identifier, title, scan)

    def register_audio_detector(self, identifier, title, detect):
        self._register(self.audio_detectors, identifier, title, detect)


def load_extensions(config, plugin_dir=None):
    from .core import PLUGIN_DIR
    from .audio import Audio
    from .services import InputHooks, current_wallpaper
    from .providers import builtin_providers
    from .library import scan_wallpapers
    from .original_audio import detect_original_audio
    registry = Registry()
    for provider in builtin_providers():
        registry.register_speech(provider)
    registry.register_wallpaper("wallpaper_engine", "Wallpaper Engine", current_wallpaper)
    registry.register_library("wallpaper_engine", "WE 本地壁纸库", scan_wallpapers)
    registry.register_audio_detector("builtin", "文件音轨 / 素材检测", detect_original_audio)
    registry.register_audio("qt", "Qt Multimedia", Audio)
    registry.register_input("pynput", "pynput 全局输入", InputHooks)
    for key, title in [("key", "快捷键"), ("mouse_left", "鼠标左键"), ("mouse_right", "鼠标右键"),
                       ("mouse_middle", "鼠标中键"), ("mouse_x1", "鼠标侧键 X1"), ("mouse_x2", "鼠标侧键 X2"),
                       ("scroll_up", "滚轮向上"), ("scroll_down", "滚轮向下"), ("any_key", "任意按键"),
                       ("random", "定时随机"), ("scheduled", "每天固定时刻"), ("startup", "绑定的壁纸开始播放")]:
        registry.register_event(key, title)
    directory = Path(plugin_dir or PLUGIN_DIR)
    for identifier in config.get("enabled_plugins", []):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", identifier):
            registry.errors.append("插件名称无效：" + str(identifier))
            continue
        try:
            path = directory / (identifier + ".py")
            spec = importlib.util.spec_from_file_location("wallpaper_companion_plugin_" + identifier, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if getattr(module, "API_VERSION", None) != API_VERSION:
                raise ValueError("不兼容的扩展 API 版本")
            # Register transactionally: a broken plugin must not leave half its capabilities.
            import copy
            staged = copy.deepcopy(registry)
            module.register(staged)
            registry = staged
            registry.loaded.append(identifier)
        except Exception as exc:
            registry.errors.append(identifier + "：" + str(exc))
    return registry
