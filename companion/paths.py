"""Machine-independent discovery; explicit UI settings always take precedence."""
import os
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def discover_wallpaper_engine():
    explicit = os.environ.get("WALLPAPER_ENGINE_DIR", "")
    roots = []
    if explicit:
        roots.append(Path(explicit).expanduser())
    try:
        import psutil
        for proc in psutil.process_iter(["name", "exe"]):
            if (proc.info["name"] or "").lower() in {"wallpaper32.exe", "wallpaper64.exe"} and proc.info["exe"]:
                roots.append(Path(proc.info["exe"]).parent)
    except (ImportError, OSError):
        pass
    steam = []
    if os.name == "nt":
        import winreg
        for hive, key, value in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")]:
            try:
                with winreg.OpenKey(hive, key) as handle:
                    steam.append(Path(winreg.QueryValueEx(handle, value)[0]))
            except OSError:
                pass
    for name in ["ProgramFiles(x86)", "ProgramFiles"]:
        if os.environ.get(name):
            steam.append(Path(os.environ[name]) / "Steam")
    for directory in list(steam):
        try:
            text = (directory / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8")
            steam.extend(Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"\n]+)"', text))
        except OSError:
            pass
    roots.extend(p / "steamapps/common/wallpaper_engine" for p in steam)
    root = next((p for p in roots if (p / "wallpaper64.exe").is_file() or (p / "wallpaper32.exe").is_file()), None)
    if root is None:
        return "", ""
    workshop = root.parent.parent / "workshop/content/431960"
    return str(root), str(workshop)


def protected_directories():
    return [Path(p) for p in discover_wallpaper_engine() if p]
