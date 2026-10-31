"""Launch system tools without inheriting the frozen application's DLL search path."""
import ctypes
import copy
import os
import subprocess
import sys
import threading
from pathlib import Path

_launch_lock = threading.RLock()
# Win32 STARTUPINFO flags not exported by every Python subprocess build.
STARTF_FORCEONFEEDBACK = 0x40
STARTF_FORCEOFFFEEDBACK = 0x80


def clean_environment(environ=None):
    env = dict(os.environ if environ is None else environ)
    for key in list(env):
        if key.upper() in {"PYTHONHOME", "PYTHONPATH"} or key.upper().startswith("_PYI_"):
            env.pop(key)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle = Path(sys._MEIPASS).resolve()
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                    if p and not Path(p).resolve().is_relative_to(bundle))
    return env


def popen_external(args, **kwargs):
    kwargs["env"] = clean_environment(kwargs.get("env"))
    if sys.platform == "win32":
        # These helpers launch background tools, not interactive windows.
        # CREATE_NO_WINDOW alone is ignored by GUI executables such as WE.
        info = copy.copy(kwargs.get("startupinfo")) if kwargs.get("startupinfo") is not None else subprocess.STARTUPINFO()
        info.dwFlags = (info.dwFlags & ~STARTF_FORCEONFEEDBACK) | subprocess.STARTF_USESHOWWINDOW | STARTF_FORCEOFFFEEDBACK
        info.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = info
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return subprocess.Popen(args, **kwargs)
    # Only hold the process-wide change during child creation, never while
    # waiting for the child. Restore even if CreateProcess raises an error.
    with _launch_lock:
        kernel = ctypes.windll.kernel32
        current = ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(current), current)
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError()
        try:
            return subprocess.Popen(args, **kwargs)
        finally:
            kernel.SetDllDirectoryW(current.value or None)


def run_external(args, *, capture_output=False, timeout=None, **kwargs):
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with popen_external(args, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
