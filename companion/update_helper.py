"""Detached updater: wait for a graceful exit, apply verified files, then restart."""
import argparse
import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

import psutil

from .paths import writable_path
from .program_update import apply_update, digest, running_instances, stage_update


def launch_environment():
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("_PYI", "_MEIPASS", "PYTHON", "CONDA", "QT", "QML"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def wait_for_parent(pid, started, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            process = psutil.Process(pid)
            if abs(process.create_time() - started) > 0.01 or not process.is_running():
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(0.2)
    raise RuntimeError("Application did not exit; update was not applied")


def apply_plan(plan, *, installer_runner=subprocess.run):
    """Called only after the parent has released files; never terminates a process."""
    target = writable_path(plan["target"])
    archive = Path(plan["archive"]).resolve()
    version = plan["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid update version")
    if type(plan["portable"]) is not bool or bool((target / "portable.flag").is_file()) != plan["portable"]:
        raise ValueError("Installation layout changed")
    if not (target / "WallpaperCompanion.exe").is_file():
        raise ValueError("Application executable is missing")
    if running_instances(target):
        raise RuntimeError("Another instance is running; no application was closed")
    suffix = "portable.zip" if plan["portable"] else "setup.exe"
    if archive.name != f"WallpaperCompanion-{version}-windows-x64-{suffix}":
        raise ValueError("Package name does not match version or layout")
    if archive.stat().st_size != plan["size"] or digest(archive) != plan["sha256"]:
        raise ValueError("Downloaded package changed; size or SHA256 mismatch")
    marker = target / "app-version.txt"
    if marker.is_file():
        current = marker.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"\d+\.\d+\.\d+", current) or tuple(map(int, version.split("."))) <= tuple(map(int, current.split("."))):
            raise ValueError("Update must be newer than the installed version")
    if plan["portable"]:
        with zipfile.ZipFile(archive) as source:
            if source.read("WallpaperCompanion/app-version.txt").decode("utf-8").strip() != version:
                raise ValueError("Portable package version does not match release")
        staged = stage_update(archive, target, plan["sha256"])
        result = apply_update(staged, target)
    else:
        command = [str(archive), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                   "/NOCLOSEAPPLICATIONS", "/NOFORCECLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS",
                   "/DIR=" + str(target), "/LOG=" + str(archive.parent / "install-update.log")]
        completed = installer_runner(command, timeout=600, env=launch_environment(),
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode != 0:
            raise RuntimeError(f"Installer failed (exit {completed.returncode}); see install-update.log")
        result = dict(applied=True, version=version)
    if (target / "app-version.txt").read_text(encoding="utf-8").strip() != version:
        raise RuntimeError("Installed version marker does not match requested version")
    return result


def run_plan(plan_path, verify_restart=None):
    plan_path = Path(plan_path).resolve()
    result_path = plan_path.parent / "result.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        wait_for_parent(plan["parent_pid"], plan["parent_started"])
        result = apply_plan(plan)
        atomic_json(result_path, {**result, "success": True})
        command = [str(Path(plan["target"]) / "WallpaperCompanion.exe")]
        if verify_restart:
            command += ["--self-test", str(Path(verify_restart).resolve())]
        subprocess.Popen(command, cwd=plan["target"], env=launch_environment(),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return 0
    except Exception as exc:
        atomic_json(result_path, dict(success=False, error=str(exc)))
        # Helper has no Qt dependency and remains usable if the application cannot start.
        if not verify_restart and os.name == "nt":
            import ctypes
            english = locals().get("plan", {}).get("language") == "en-US"
            caption = "Update failed" if english else "更新未完成"
            message = ("Update was not completed. Files and logs have been retained.\n" if english else
                       "更新未完成，安装包和日志已保留。\n") + str(exc) + "\n" + str(result_path)
            ctypes.windll.user32.MessageBoxW(None, message, caption, 0x10)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--verify-restart", type=Path, help="Isolated distribution verification only")
    args = parser.parse_args()
    return run_plan(args.plan, args.verify_restart)
