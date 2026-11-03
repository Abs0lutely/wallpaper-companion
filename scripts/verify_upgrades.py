"""Cloud-only gate: upgrade actual previous binaries using the new detached helper."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from companion.program_update import digest, personal_snapshot
from companion.update_helper import atomic_json, launch_environment
from verify_windows import check_exe


def check_assets(directory):
    sums = {}
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
        checksum, name = line.split(maxsplit=1)
        if Path(name).name != name:
            raise ValueError("Invalid checksum filename")
        sums[name] = checksum
    files = []
    for suffix in ("portable.zip", "setup.exe"):
        matches = list(directory.glob("*-" + suffix))
        if len(matches) != 1 or digest(matches[0]) != sums.get(matches[0].name):
            raise ValueError("Missing or incorrect release asset: " + suffix)
        files.append(matches[0].resolve())
    return files


def run_helper(helper, target, archive, version, portable, output, env):
    folder = output / ("portable-helper" if portable else "installed-helper")
    folder.mkdir()
    detached = folder / helper.name
    shutil.copy2(helper, detached)
    if not portable:
        # Inno writes its log next to the package. Keep test artifacts out of dist/release.
        archive = Path(shutil.copy2(archive, folder / archive.name))
    # A real exited process gives the handoff a concrete, non-running parent identity.
    import psutil
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"], creationflags=subprocess.CREATE_NO_WINDOW)
    started = psutil.Process(parent.pid).create_time()
    parent.wait(timeout=5)
    plan = dict(target=str(target), archive=str(archive), version=version, portable=portable,
                sha256=digest(archive), size=archive.stat().st_size,
                parent_pid=parent.pid, parent_started=started, language="en-US")
    atomic_json(folder / "handoff.json", plan)
    report = output / ("upgrade-portable-restart.json" if portable else "upgrade-installed-restart.json")
    completed = subprocess.run([str(detached), "--plan", str(folder / "handoff.json"), "--verify-restart", str(report)],
                               env=env, cwd=folder, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    assert completed.returncode == 0 and result.get("success"), result
    deadline = time.monotonic() + 80
    while not report.exists() and time.monotonic() < deadline:
        time.sleep(0.25)
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["passed"] and data["frozen"], data
    # Self-test writes the report just before exiting; wait for its process to release files.
    from companion.program_update import running_instances
    deadline = time.monotonic() + 15
    while running_instances(target) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not running_instances(target)
    assert (target / "app-version.txt").read_text().strip() == version
    return result


def add_personal_files(app, data):
    fixtures = {
        data / "config.json": '{"profiles":[],"run_mode":"standalone","auto_update_enabled":false}',
        data / "audio/voice/personal.wav": "personal audio sentinel",
        data / "packs/keep/pack.json": "personal pack sentinel",
        data / "packs/keep/voice/keep.wav": "pack audio sentinel",
        app / "shared/voice/shared.wav": "shared audio sentinel",
        app / "shared/dialogues.json": "shared dialogue sentinel",
        app / "plugins/personal.py": "# user plugin sentinel",
    }
    for path, body in fixtures.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return {path: digest(path) for path in fixtures}


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "win32":
        raise RuntimeError("Run upgrade installation tests only on a disposable Windows Actions runner")
    import winreg
    key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{7D64A36F-58DA-47D5-9BC7-3F10CD22D328}_is1"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
            raise RuntimeError("An installation already exists; refusing to replace it")
    except FileNotFoundError:
        pass
    old_zip, old_setup = check_assets(ROOT / "output/upgrade-baseline")
    archive, installer = check_assets(ROOT / "dist/release")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    output = ROOT / "output"
    with tempfile.TemporaryDirectory(prefix="upgrade 中文 ", dir=output) as tmp:
        temp = Path(tmp)
        env = launch_environment()
        env.pop("WALLPAPER_COMPANION_DATA", None)
        env["LOCALAPPDATA"] = str(temp / "local user")
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32") + os.pathsep + os.environ["SystemRoot"]
        with zipfile.ZipFile(old_zip) as z: z.extractall(temp / "portable")
        portable = temp / "portable/WallpaperCompanion"
        helper = ROOT / "dist/WallpaperCompanion/WallpaperCompanionUpdater.exe"
        assert helper.is_file()
        before = add_personal_files(portable, portable / "data")
        program_before = personal_snapshot(portable)
        result_portable = run_helper(helper, portable, archive, version, True, output, env)
        assert all(digest(path) == checksum for path, checksum in before.items())
        assert personal_snapshot(portable) == program_before
        install = temp / "installed app"
        subprocess.run([str(old_setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/NOICONS", "/TASKS=",
                        "/DIR=" + str(install)], env=env, check=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            before = add_personal_files(install, Path(env["LOCALAPPDATA"]) / "WallpaperCompanion")
            result_installed = run_helper(helper, install, installer, version, False, output, env)
            assert all(digest(path) == checksum for path, checksum in before.items())
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as handle:
                assert Path(winreg.QueryValueEx(handle, "InstallLocation")[0]).resolve() == install.resolve()
                assert winreg.QueryValueEx(handle, "DisplayVersion")[0] == version
        finally:
            subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                           env=env, check=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        for path, checksum in before.items():
            if path.name == "personal.py":
                continue  # User plugin is not installer-owned and is separately verified above.
            assert digest(path) == checksum
        report = dict(passed=True, baseline="v0.11.0", target=version, detached_frozen_helper=True,
                      portable_upgrade=True, installed_upgrade=True, restarted_exe_selftests=True,
                      data_audio_plugins_packs_preserved=True, same_install_directory=True)
        atomic_json(output / "upgrade-verification.json", report)
        print(json.dumps(report))


if __name__ == "__main__":
    main()
