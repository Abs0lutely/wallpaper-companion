"""Source, portable and installed layouts; never store user data in _internal."""
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Layout:
    app_dir: Path
    data_dir: Path
    plugin_dir: Path
    frozen: bool
    portable: bool
    shared_dir: Path


def runtime_layout(*, frozen=None, executable=None, source_root=None, environ=None):
    env = os.environ if environ is None else environ
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    app = (Path(executable or sys.executable).resolve().parent if frozen else
           Path(source_root or Path(__file__).resolve().parent.parent).resolve())
    portable = frozen and (app / "portable.flag").is_file()
    if env.get("WALLPAPER_COMPANION_DATA"):
        data = Path(env["WALLPAPER_COMPANION_DATA"]).expanduser().resolve()
    elif frozen and not portable:
        local = Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        data = (local / "WallpaperCompanion").resolve()
    else:
        data = app / "data"
    plugins = data / "plugins" if frozen and not portable else app / "plugins"
    shared = data / "shared" if env.get("WALLPAPER_COMPANION_DATA") else app / "shared"
    return Layout(app, data, plugins, frozen, portable, shared)


LAYOUT = runtime_layout()
