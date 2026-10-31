"""Local release gate. No Git, network publishing or personal-install updates."""
import hashlib
import importlib.metadata as metadata
import json
import os
import struct
import subprocess
import sys
import tomllib
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dependencies_ready(root):
    """Read pinned requirements without requiring packaging to be installed first."""
    for file in ("requirements.txt", "requirements-build.txt"):
        for line in (root / file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-r")):
                continue
            name, separator, expected = line.partition("==")
            if not separator:
                return False
            try:
                if metadata.version(name) != expected:
                    return False
            except metadata.PackageNotFoundError:
                return False
    return True


def promote(stage, destination, report):
    """Expose only this run's verified bytes; never use an older success report."""
    if json.loads(report.read_text(encoding="utf-8")).get("passed") is not True:
        raise RuntimeError("Final verification did not pass")
    sums = stage / "SHA256SUMS.txt"
    names = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        if Path(name).name != name or not name.endswith(("-portable.zip", "-setup.exe")):
            raise RuntimeError("Unexpected artifact name")
        if hashlib.sha256((stage / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Artifact changed after verification")
        names.append(name)
    if len(names) != 2 or len(set(names)) != 2 or not any(n.endswith("-setup.exe") for n in names) or not any(n.endswith("-portable.zip") for n in names):
        raise RuntimeError("Expected exactly one ZIP and one installer")
    # Rename within dist only after every file has passed. No partial public folder.
    if destination.exists():
        raise FileExistsError(destination)
    stage.rename(destination)


def pipeline(root, work, stage, destination, run, ready=dependencies_ready):
    py = sys.executable
    if not ready(root):
        run([py, "-m", "pip", "install", "-r", "requirements-build.txt"])
    run([py, "-m", "pip", "check"])
    run([py, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
    run([py, "-m", "compileall", "-q", "companion", "main.py", "scripts"])
    if not (root / "build/tools/inno/ISCC.exe").is_file():
        run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/bootstrap_inno.ps1"])
    run([py, "scripts/build_windows.py", "--release-dir", str(stage)])
    reports = work / "verification"
    run([py, "scripts/verify_windows.py", "--release-dir", str(stage), "--report-dir", str(reports)])
    promote(stage, destination, reports / "release-verification.json")


def main():
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        raise RuntimeError("Run on Windows x64 using the project Conda environment")
    import msvcrt
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    with (output / "local-release.lock").open("a+b") as lock:
        if os.fstat(lock.fileno()).st_size == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("Another local build is running. Wait for it to finish.") from None
        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        if len(version.split(".")) != 3 or not all(p.isascii() and p.isdecimal() for p in version.split(".")):
            raise ValueError("Set a numeric X.Y.Z version in pyproject.toml first")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        work = output / "local-release" / stamp
        work.mkdir(parents=True)
        stage = ROOT / "dist/.release-staging" / stamp
        destination = ROOT / "dist/verified" / version / stamp
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"Version: {version}\nLog: {work / 'build.log'}", flush=True)
        with (work / "build.log").open("w", encoding="utf-8") as log:
            def run(command):
                label = subprocess.list2cmdline([str(arg) for arg in command])
                print("\n> " + label, flush=True)
                log.write("\n> " + label + "\n")
                log.flush()
                env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
                with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
                    for line in process.stdout:
                        print(line, end="", flush=True)
                        log.write(line)
                        log.flush()
                    if process.wait():
                        raise subprocess.CalledProcessError(process.returncode, command)
            try:
                pipeline(ROOT, work, stage, destination, run)
            except Exception as error:
                log.write(f"\nFAILED: {error}\n")
                print(f"\nFAILED: {error}\nNo verified output for this run. Log: {work / 'build.log'}", flush=True)
                return 1
        print(f"\nVERIFIED: {destination}\nUpload these THREE files manually; no Git operations were performed.", flush=True)
        if os.environ.get("WALLPAPER_BUILD_NO_OPEN") != "1":
            try:
                os.startfile(destination)
            except OSError as error:
                print(f"Open the verified folder manually: {error}", flush=True)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        sys.exit(1)
