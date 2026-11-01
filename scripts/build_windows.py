"""Build redistributable Windows x64 folder, portable ZIP and per-user installer."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import shutil
import struct
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def prepare():
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter, QColor, QPen
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(QColor("#111827"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#5eead4"), 15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for x, top, bottom in [(60, 104, 152), (94, 70, 186), (128, 42, 214), (162, 70, 186), (196, 104, 152)]:
        painter.drawLine(x, top, x, bottom)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    png = bytes(data)
    (build / "app.ico").write_bytes(struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png)
    numbers = tuple(map(int, version().split("."))) + (0,)
    (build / "version.txt").write_text(
        f"VSVersionInfo(ffi=FixedFileInfo(filevers={numbers!r}, prodvers={numbers!r}, mask=0x3f, flags=0, OS=0x40004, fileType=0x1, subtype=0, date=(0,0)), "
        f"kids=[StringFileInfo([StringTable('040904B0', [StringStruct('ProductName','Wallpaper Companion'), StringStruct('FileDescription','Wallpaper Companion'), StringStruct('FileVersion','{version()}'), StringStruct('ProductVersion','{version()}'), StringStruct('OriginalFilename','WallpaperCompanion.exe')])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])",
        encoding="utf-8")


def copy_licenses(bundle):
    from packaging.requirements import Requirement
    target = bundle / "licenses"
    shutil.copytree(ROOT / "packaging/licenses", target, dirs_exist_ok=True)
    pending = ["PySide6", "pynput", "requests", "psutil", "keyring", "PyYAML", "PyInstaller"]
    seen = set()
    distributions = []
    while pending:
        name = pending.pop()
        normalized = name.lower().replace("_", "-").replace(".", "-")
        if normalized in seen:
            continue
        seen.add(normalized)
        dist = metadata.distribution(name)
        distributions.append(dist)
        for raw in dist.requires or []:
            requirement = Requirement(raw)
            if not requirement.marker or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    for dist in distributions:
        name = dist.metadata.get("Name", "unknown")
        for path in dist.files or []:
            if any(word in path.name.lower() for word in ["license", "copying", "copyright", "notice"]):
                source = Path(dist.locate_file(path))
                if source.is_file() and source.stat().st_size < 2_000_000:
                    relative = Path(str(path).replace("\\", "/"))
                    if ".." in relative.parts:
                        continue
                    dest = target / name / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
    python_license = next((Path(sys.base_prefix) / name for name in ["LICENSE.txt", "LICENSE_PYTHON.txt", "Lib/LICENSE.txt"]
                           if (Path(sys.base_prefix) / name).is_file()), None)
    if python_license is None:
        raise ValueError("Python license not found in build environment")
    shutil.copy2(python_license, target / "Python-LICENSE.txt")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", type=Path, default=ROOT / "build/tools/inno/ISCC.exe")
    parser.add_argument("--skip-freeze", action="store_true", help="Reuse existing frozen binaries after documentation-only changes")
    parser.add_argument("--release-dir", type=Path, default=ROOT / "dist/release")
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        parser.error("Build on Windows x64 using 64-bit Python")
    # Do not ship a default-on experience without its promised voice assets.
    sys.path.insert(0, str(ROOT))
    from companion.operation_pack import require_pack
    require_pack(ROOT / "examples/audio/operation-voice")
    prepare()
    if not args.skip_freeze:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(ROOT / "dist"),
                        "--workpath", str(ROOT / "build/pyinstaller"), str(ROOT / "packaging/wallpaper-companion.spec")], cwd=ROOT, check=True)
    bundle = ROOT / "dist/WallpaperCompanion"
    assert (bundle / "WallpaperCompanion.exe").is_file()
    for name in ["README.md", "USER_GUIDE.md", "EXTENSIONS.md", "THIRD_PARTY.md", "LICENSE", "BUILDING.md", "RELEASE_GUIDE.md"]:
        shutil.copy2(ROOT / name, bundle / name)
    shutil.copytree(ROOT / "examples", bundle / "examples", ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    shutil.copytree(ROOT / "readme-assets", bundle / "readme-assets", dirs_exist_ok=True)
    (bundle / "plugins").mkdir(exist_ok=True)
    copy_licenses(bundle)
    release = args.release_dir.resolve()
    release.mkdir(parents=True, exist_ok=True)
    prefix = f"WallpaperCompanion-{version()}-windows-x64"
    archive = release / (prefix + "-portable.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for file in sorted(bundle.rglob("*")):
            if file.is_file():
                relative = file.relative_to(bundle)
                if any(part in {"data", "shared", "output", "__pycache__"} for part in relative.parts):
                    raise ValueError("Refusing to distribute user/generated data: " + str(relative))
                z.write(file, "WallpaperCompanion/" + relative.as_posix())
        z.writestr("WallpaperCompanion/portable.flag", "Keep this file for portable data storage.\n")
    if not args.iscc.is_file():
        raise SystemExit("Inno compiler missing. Run scripts/bootstrap_inno.ps1 or pass --iscc PATH")
    subprocess.run([str(args.iscc.resolve()), "/Qp", f"/DAppVersion={version()}", f"/DBundleDir={bundle}",
                    f"/DReleaseDir={release}", str(ROOT / "packaging/installer.iss")], cwd=ROOT, check=True)
    files = [archive, release / (prefix + "-setup.exe")]
    checksums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files)
    (release / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    print(json.dumps({"version": version(), "artifacts": [{"name": p.name, "bytes": p.stat().st_size} for p in files]}))


if __name__ == "__main__":
    main()
