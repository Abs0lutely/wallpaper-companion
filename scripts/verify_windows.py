"""Verify the exact release ZIP, frozen executable and installer/uninstaller."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_exe(exe, report, env):
    result = subprocess.run([str(exe), "--self-test", str(report)], env=env, cwd=exe.parent,
                            timeout=70, creationflags=subprocess.CREATE_NO_WINDOW)
    if not report.is_file():
        raise RuntimeError(f"EXE did not produce a self-test report (exit {result.returncode})")
    data = json.loads(report.read_text(encoding="utf-8"))
    if result.returncode or not data.get("passed") or not data.get("frozen"):
        raise RuntimeError("Frozen self-test failed: " + json.dumps(data, ensure_ascii=True))
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, default=ROOT / "dist/release")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Windows verification requires Windows")
    import winreg
    uninstall_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{7D64A36F-58DA-47D5-9BC7-3F10CD22D328}_is1"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
            raise RuntimeError("A real installation exists. Verify in another user/VM to avoid changing it.")
    except FileNotFoundError:
        pass
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    prefix = f"WallpaperCompanion-{version}-windows-x64"
    archive = args.release_dir / (prefix + "-portable.zip")
    installer = args.release_dir / (prefix + "-setup.exe")
    sums = {line.split(maxsplit=1)[1]: line.split(maxsplit=1)[0]
            for line in (args.release_dir / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()}
    for file in [archive, installer]:
        assert hashlib.sha256(file.read_bytes()).hexdigest() == sums[file.name], "SHA256 mismatch"
    output = args.report_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release 中文 ", dir=output) as temporary:
        temp = Path(temporary)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "CONDA", "QT", "QML"))
               and k.upper() not in {"WALLPAPER_COMPANION_DATA", "VIRTUAL_ENV", "_MEIPASS2", "_PYI_APPLICATION_HOME_DIR", "_PYI_ARCHIVE_FILE", "_PYI_PARENT_PROCESS_LEVEL"}}
        windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        env["PATH"] = os.pathsep.join(str(windows / p) for p in ["System32", "", "System32/Wbem"])
        env["LOCALAPPDATA"] = str(temp / "local-user-data")
        with zipfile.ZipFile(archive) as z:
            assert all(not Path(p).is_absolute() and ".." not in Path(p).parts for p in z.namelist())
            z.extractall(temp / "portable app")
        portable = temp / "portable app/WallpaperCompanion"
        p = check_exe(portable / "WallpaperCompanion.exe", output / "frozen-portable.json", env)
        assert p["portable"] and Path(p["data_dir"]) == portable / "data"
        assert all((portable / name).is_file() for name in ["licenses/LGPL-3.0-only.txt", "licenses/GPL-3.0-only.txt", "licenses/Python-LICENSE.txt"])
        install = temp / "installed app"
        subprocess.run([str(installer.resolve()), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/NOICONS", "/TASKS=",
                        "/DIR=" + str(install), "/LOG=" + str(output / "install-test.log")], check=True, timeout=180,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            assert not (install / "portable.flag").exists()
            i = check_exe(install / "WallpaperCompanion.exe", output / "frozen-installed.json", env)
            expected_data = temp / "local-user-data/WallpaperCompanion"
            assert not i["portable"] and Path(i["data_dir"]) == expected_data
            expected_data.mkdir(parents=True, exist_ok=True)
            sentinel = expected_data / "preserve-user-data.txt"
            sentinel.write_text("do not delete", encoding="utf-8")
            shared_sentinel = install / "shared/preserve-shared-audio.txt"
            shared_sentinel.parent.mkdir(exist_ok=True)
            shared_sentinel.write_text("keep shared audio", encoding="utf-8")
        finally:
            subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                            "/LOG=" + str(output / "uninstall-test.log")], check=True, timeout=180,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        assert not (install / "WallpaperCompanion.exe").exists()
        assert sentinel.read_text(encoding="utf-8") == "do not delete"
        assert shared_sentinel.read_text(encoding="utf-8") == "keep shared audio"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
                raise AssertionError("Installer registration not removed")
        except FileNotFoundError:
            pass
        result = {"passed": True, "portable_checks": p["checks"], "installed_checks": i["checks"],
                  "clean_path": True, "unicode_and_spaces": True, "install_and_uninstall": True,
                  "user_data_preserved": True, "shared_resources_preserved": True, "sha256_verified": True}
        (output / "release-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
