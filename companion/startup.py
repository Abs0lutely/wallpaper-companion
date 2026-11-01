"""Opt-in per-user Windows login startup. No administrator privileges needed."""
from .i18n import tr
import os
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "WallpaperVoiceCompanion"


def startup_command():
    from .core import ROOT
    if getattr(sys, "frozen", False):
        args = [sys.executable, "--tray"]
    else:
        python = Path(sys.executable)
        windowed = python.with_name("pythonw.exe")
        if windowed.is_file():
            python = windowed
        args = [str(python), str(ROOT / "main.py"), "--tray"]
    command = subprocess.list2cmdline(args)
    if len(command) > 260:
        raise ValueError(tr('ui.a3e75920616b', '程序路径过长，超出 Windows Run 启动项限制，请移到较短目录'))
    return command


def startup_enabled(name=VALUE_NAME):
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return bool(value)
    except FileNotFoundError:
        return False


def set_startup(enabled, name=VALUE_NAME):
    if os.name != "nt":
        raise ValueError(tr('ui.bf5fb5de3548', '开机自启目前仅支持 Windows'))
    import winreg
    command = startup_command() if enabled else None
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
