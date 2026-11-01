from __future__ import annotations
from .i18n import tr

import ctypes
import json
import locale
import os
import subprocess
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import psutil
import requests

from .core import writable_path, DATA, save_generated
from .external import run_external, popen_external

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def running_wallpaper_processes():
    found = []
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            if (proc.info["name"] or "").lower() in {"wallpaper32.exe", "wallpaper64.exe"}:
                found.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def current_wallpaper(config):
    processes = running_wallpaper_processes()
    if not processes:
        return dict(path="", title=tr('ui.6cd64300ab4e', 'Wallpaper Engine 未运行'), running=False)
    root = Path(config["we_dir"])
    exe = next((Path(p["exe"]) for p in processes if p.get("exe") and Path(p["exe"]).parent == root), None)
    if not exe:
        raise ValueError(tr('ui.a862efb3f772', '发现 Wallpaper Engine 进程，但安装目录不匹配；请在设置中选择实际目录。'))
    # Timers also run in the tray/over fullscreen applications. Never launch
    # WE's GUI executable from a background poll: CREATE_NO_WINDOW only hides
    # consoles, and invoking WE can activate/redraw its existing windows.
    if not config.get("_wallpaper_command_query", False):
        return selected_wallpaper(config, source=tr('ui.16f4c787477c', '已保存配置（只读轮询）'))
    result = run_external([str(exe), "-control", "getWallpaper", "-monitor", str(config.get("monitor", 0))],
                            capture_output=True, timeout=5, creationflags=NO_WINDOW)
    raw = result.stdout
    if result.returncode:
        raise RuntimeError(tr('ui.5003ef7789b0', '查询当前壁纸失败，退出码 {value0}', value0=result.returncode))
    values = []
    encodings = ["utf-16" if b"\x00" in raw else "utf-8-sig", "utf-8-sig", locale.getpreferredencoding(False), "gb18030"]
    for encoding in encodings:
        try:
            value = raw.decode(encoding).strip().strip('"')
            if value:
                values.append(value)
                if Path(value).exists():
                    break
        except (UnicodeError, OSError, ValueError):
            continue
    path = next((v for v in values if Path(v).exists()), "")
    if not path:
        return selected_wallpaper(config)
    return wallpaper_info(path, tr('ui.0cb15544cc0d', '官方查询'))


def wallpaper_info(path, source):
    project = Path(path) if Path(path).name.lower() == "project.json" else Path(path).parent / "project.json"
    title = Path(path).parent.name
    try:
        title = json.loads(project.read_text(encoding="utf-8-sig")).get("title", title)
    except (OSError, ValueError):
        pass
    return dict(path=path, title=title, running=True, source=source)


def selected_wallpaper(config, source=tr('ui.4bec7e4cc5e7', '已保存配置（官方查询无输出）')):
    """Read only current selectedwallpapers, never recent history or last browser selection.

    Some Windows builds return no stdout for getWallpaper. This reports saved selection
    explicitly: WE can lag writing config, so this is not a claim of live playback state.
    """
    data = json.loads((Path(config["we_dir"]) / "config.json").read_text(encoding="utf-8-sig"))
    accounts = {key: value for key, value in data.items() if isinstance(value, dict)
                and "wallpaperconfig" in value.get("general", {})}
    account = accounts.get(os.environ.get("USERNAME", ""))
    if account is None:
        if len(accounts) != 1:
            raise ValueError(tr('ui.5440da0eeae3', 'WE 保存配置存在多个用户，无法可靠确定当前配置。'))
        account = next(iter(accounts.values()))
    selected = account["general"]["wallpaperconfig"].get("selectedwallpapers", {})
    entry = selected.get("Monitor" + str(config.get("monitor", 0)), {})
    path = entry.get("file", "")
    if not path or not Path(path).is_file():
        return dict(path="", title=tr('ui.d7502775862e', '该屏幕没有有效的已保存壁纸路径'), running=True, source=tr('ui.b4cc36ab4d2f', '已保存配置'))
    return wallpaper_info(path, source)


def foreground_state():
    """Only class/geometry/PID; never collect window titles or typed text."""
    if os.name != "nt":
        return dict(desktop=True, fullscreen=False, own=False)
    from ctypes import wintypes
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user.MonitorFromWindow.restype = wintypes.HANDLE
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    hwnd = user.GetForegroundWindow()
    cls = ctypes.create_unicode_buffer(256)
    user.GetClassNameW(hwnd, cls, 256)
    desktop = cls.value in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    own = pid.value == os.getpid()
    rect = wintypes.RECT()
    monitor = MONITORINFO()
    monitor.cbSize = ctypes.sizeof(monitor)
    full = False
    if hwnd and not desktop and not own and user.GetWindowRect(hwnd, ctypes.byref(rect)):
        if user.GetMonitorInfoW(user.MonitorFromWindow(hwnd, 2), ctypes.byref(monitor)):
            m = monitor.rcMonitor
            full = rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
    return dict(desktop=desktop, fullscreen=full, own=own)


def local_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
        raise ValueError(tr('ui.82819a2c413f', '请填写本机 HTTP 地址，例如 http://127.0.0.1:9880'))
    return value.rstrip("/")


def session():
    client = requests.Session()
    client.trust_env = False
    return client


def api_status(settings):
    with session() as client:
        response = client.get(local_url(settings["url"]) + "/openapi.json", timeout=4)
        response.raise_for_status()
        if "/tts" not in response.json().get("paths", {}):
            raise ValueError(tr('ui.750a473ef439', '该地址没有 api_v2 /tts 接口'))
    return tr('ui.baa6111d1b4e', 'GPT-SoVITS 接口已就绪')


def start_api(settings, protected=()):
    """Compatibility entry point; normal UI starts only during synthesis."""
    from .managed_api import api
    return api.ensure(settings, protected)


def generation_status(callback, phase, completed, total, message):
    if callback:
        callback(dict(phase=phase, completed=completed, total=total, message=message))


def generation_duplicates(lines, output, protected=(), entries=None, model_name=None):
    """Read-only preflight, including duplicate names within the planned batch."""
    from .core import filename_for
    from .audio_names import stems_with_copies, has_audio
    root = writable_path(output, protected)
    cache, seen, duplicates = {}, set(), []
    for index, text in enumerate(lines):
        category = entries[index]["category"] if entries is not None else ""
        folder = writable_path(root / category, protected)
        if category not in cache:
            from .core import audio_files
            cache[category] = stems_with_copies({p.stem.casefold() for p in audio_files(str(folder), recursive=entries is None) if p.stat().st_size > 0})
        stem = Path(filename_for(text,model_name)).stem.casefold()
        key = category, stem
        exists = has_audio(cache[category],text,model_name)
        if exists or key in seen:
            duplicates.append(dict(index=index, text=text, category=category, existing=exists,model=model_name or ""))
        seen.add(key)
    return duplicates


def generate(settings, lines, output, protected=(), progress=None, provider=None, cancel=None, status=None, skip_existing=False):
    writable_path(output, protected)
    if provider is None:
        from .providers import builtin_providers
        provider = next(p for p in builtin_providers() if p.id == "gpt_sovits")
    if getattr(provider, "id", "") == "gpt_sovits":
        settings = {**settings, "_protected_dirs": list(protected), "_tts_batch_id": settings.get("_tts_batch_id") or uuid.uuid4().hex}
    paths = []
    from .core import audio_files, filename_for
    from .audio_names import stems_with_copies, has_audio
    model_name = settings.get("_filename_model")
    existing = stems_with_copies({p.stem.casefold() for p in audio_files(str(output)) if p.stat().st_size > 0}) if skip_existing else set()
    generation_status(status, "prepare", 0, len(lines), tr('ui.0aaa57213850', '准备生成 {value0} 条语音。', value0=len(lines)))
    for index, text in enumerate(lines):
        try:
            if cancel is not None and cancel.is_set():
                raise RuntimeError(tr('ui.6f4b8d014592', '语音生成已取消'))
            stem = Path(filename_for(text,model_name)).stem.casefold()
            if skip_existing and has_audio(existing,text,model_name):
                generation_status(status, "skipped", index+1, len(lines), tr('ui.615b083dec07', '{value0}/{value1} 已存在，跳过：{value2}', value0=index + 1, value1=len(lines), value2=text))
                continue
            generation_status(status, "synthesis", index, len(lines), tr('ui.d4849af9a8dd', '正在生成第 {value0}/{value1} 条，等待服务返回音频…', value0=index + 1, value1=len(lines)))
            current = settings
            if getattr(provider, "id", "") == "gpt_sovits" and status:
                current = {**settings, "_tts_status": lambda message: generation_status(status, "api", index, len(lines), message)}
            data = provider.synthesize(current, text)
            if cancel is not None and cancel.is_set():
                raise RuntimeError(tr('ui.6f4b8d014592', '语音生成已取消'))
            generation_status(status, "saving", index, len(lines), tr('ui.bee4a0bacf46', '正在验证并保存第 {value0}/{value1} 条 WAV…', value0=index + 1, value1=len(lines)))
            path = save_generated(output, text, data, protected, model_name=model_name)
            paths.append(str(path))
            existing.add(stem)
            generation_status(status, "saved", index+1, len(lines), tr('ui.ff65b09a6e1c', '已保存 {value0}/{value1}：{value2}', value0=index + 1, value1=len(lines), value2=path.name))
            if progress:
                progress(tr('ui.64b295927966', '{value0}/{value1} 已保存：{value2}', value0=index + 1, value1=len(lines), value2=path.name))
        except Exception as exc:
            generation_status(status, "failed", len(paths), len(lines), tr('ui.b08f680a2ad9', '第 {value0} 条未完成；已保存 {value1} 条保留。', value0=index + 1, value1=len(paths)))
            raise ValueError(tr('ui.4469bc20aba6', '第 {value0} 条失败：{value1}；已保存 {value2} 条保留在目录中。', value0=index + 1, value1=exc, value2=len(paths))) from exc
    return paths


def generate_dialogue_entries(settings, entries, output, protected=(), progress=None, provider=None, skip_existing=True, cancel=None, status=None):
    settings = {**settings, "_tts_batch_id": uuid.uuid4().hex}
    from .core import filename_for, AUDIO_EXTENSIONS
    from .audio_names import stems_with_copies, has_audio
    model_name = settings.get("_filename_model")
    from .dialogues import normalize_dialogues
    entries = [entry for entry in normalize_dialogues(entries) if entry["enabled"]]
    # Validate all output locations before any API call.
    root = writable_path(output, protected)
    folders = {entry["category"]: writable_path(root / entry["category"], protected) for entry in entries}
    paths, skipped = [], 0
    generation_status(status, "prepare", 0, len(entries), tr('ui.facf0d921992', '准备按分类处理 {value0} 条台词。', value0=len(entries)))
    existing = {}
    for category, folder in folders.items():
        existing[category] = stems_with_copies({p.stem.casefold() for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and p.stat().st_size > 0}) if folder.is_dir() else set()
    for i, entry in enumerate(entries):
        if cancel is not None and cancel.is_set():
            raise RuntimeError(tr('ui.6f4b8d014592', '语音生成已取消'))
        category, text = entry["category"], entry["text"]
        stem = Path(filename_for(text,model_name)).stem.casefold()
        if skip_existing and has_audio(existing[category],text,model_name):
            skipped += 1
            generation_status(status, "skipped", i+1, len(entries), tr('ui.615b083dec07', '{value0}/{value1} 已存在，跳过：{value2}', value0=i + 1, value1=len(entries), value2=text))
            if progress:
                progress(tr('ui.4a6cff6ef1cb', '{value0}/{value1} 已有音频，跳过：{value2}', value0=i + 1, value1=len(entries), value2=text))
            continue
        try:
            def item_status(event):
                completed = i+1 if event["phase"] == "saved" else i
                generation_status(status, event["phase"], completed, len(entries), tr('ui.1a49cc9bfece', '分类 {value0} · 第{value1}/{value2}条：{value3}', value0=category, value1=i + 1, value2=len(entries), value3=event['message']))
            generated = generate(settings, [text], folders[category], protected, provider=provider, cancel=cancel, status=item_status if status else None)
            paths.extend(generated)
            existing[category].add(stem)
            if progress:
                progress(tr('ui.6d992036174a', '{value0}/{value1} 已保存 {value2}：{value3}', value0=i + 1, value1=len(entries), value2=category, value3=text))
        except Exception as exc:
            raise ValueError(tr('ui.bcc83004e5f7', '台词库第 {value0} 条失败：{value1}；已新增 {value2} 条保留在分类目录中。', value0=i + 1, value1=exc, value2=len(paths))) from exc
    return dict(paths=paths, skipped=skipped)


class InputHooks:
    def __init__(self, emit):
        self.emit = emit
        self.lock = threading.Lock()
        self.hotkeys = []
        self.any_key = False
        self.keyboard_listener = None
        self.mouse_listener = None

    def configure(self, rules):
        from pynput import keyboard
        with self.lock:
            self.any_key = any(r.get("enabled", True) and r["event"] == "any_key" for r in rules)
            self.hotkeys = []
            for rule in rules:
                if rule.get("enabled", True) and rule["event"] == "key":
                    self.hotkeys.append(keyboard.HotKey(keyboard.HotKey.parse(rule["hotkey"]),
                                        lambda rid=rule["id"]: self.emit("key", rid)))

    def start(self):
        from pynput import keyboard, mouse
        def press(key):
            with self.lock:
                for hotkey in self.hotkeys:
                    hotkey.press(self.keyboard_listener.canonical(key))
                if self.any_key:
                    self.emit("any_key", "")
        def release(key):
            with self.lock:
                for hotkey in self.hotkeys:
                    hotkey.release(self.keyboard_listener.canonical(key))
        def click(x, y, button, pressed):
            if pressed:
                self.emit("mouse_" + button.name, "")
        def scroll(x, y, dx, dy):
            if dy:
                self.emit("scroll_up" if dy > 0 else "scroll_down", "")
        self.keyboard_listener = keyboard.Listener(on_press=press, on_release=release)
        self.mouse_listener = mouse.Listener(on_click=click, on_scroll=scroll)
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop(self):
        for listener in [self.keyboard_listener, self.mouse_listener]:
            if listener:
                listener.stop()
