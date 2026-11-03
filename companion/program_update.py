"""Program-only portable replacement, shared by CLI and frozen update helper."""
import hashlib
import json
import os
import re
import uuid
import zipfile
from pathlib import Path, PureWindowsPath
import psutil
from .core import writable_path

PROGRAM_ROOTS = {"WallpaperCompanion.exe", "WallpaperCompanionUpdater.exe", "app-version.txt", "_internal", "examples", "licenses", "readme-assets", "README.md", "README.en.md", "USER_GUIDE.md", "USER_GUIDE.en.md", "USAGE.md", "USAGE.en.md", "COMPANION_PACKS.md", "COMPANION_PACKS.en.md",
                 "EXTENSIONS.md", "THIRD_PARTY.md", "LICENSE", "BUILDING.md", "RELEASE_GUIDE.md"}
UPDATE_ROOTS = {".program-updates", ".program-backups"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def checked_child(root, name):
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.resolve() == root.resolve():
        raise ValueError("更新路径超出目标目录或包含链接：" + str(path))
    return path


def personal_snapshot(target):
    result = {}
    for directory, subdirs, files in os.walk(target, followlinks=False):
        folder = Path(directory)
        if folder == target:
            subdirs[:] = [n for n in subdirs if n not in PROGRAM_ROOTS | UPDATE_ROOTS]
        for name in files:
            path = folder / name
            relative = path.relative_to(target)
            if relative.parts[0] not in PROGRAM_ROOTS | UPDATE_ROOTS:
                result[relative.as_posix()] = digest(path)
    return result


def running_instances(target):
    found = []
    expected = (target / "WallpaperCompanion.exe").resolve()
    for process in psutil.process_iter(["name", "exe"]):
        try:
            if (process.info.get("name") or "").lower() != "wallpapercompanion.exe":
                continue
            if not process.info.get("exe"):
                raise RuntimeError("无法确认某个声伴进程的位置，暂不替换程序")
            if Path(process.info["exe"]).resolve() == expected:
                found.append(process.pid)
        except psutil.NoSuchProcess:
            continue
    return found


def stage_update(archive, target, expected_sha256):
    archive, target = Path(archive).resolve(), writable_path(target)
    if not (target / "portable.flag").is_file() or not (target / "WallpaperCompanion.exe").is_file():
        raise ValueError("目标不是已有的免安装版目录")
    if digest(archive) != expected_sha256.lower():
        raise ValueError("ZIP SHA256 校验失败")
    match = re.fullmatch(r"WallpaperCompanion-(\d+\.\d+\.\d+)-windows-x64-portable\.zip", archive.name)
    if not match:
        raise ValueError("不是受支持的免安装发行包文件名")
    # Validate all archive entries before creating anything in the target.
    entries = []
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist()) > 20000 or sum(p.file_size for p in z.infolist()) > 2 * 1024**3:
            raise ValueError("发行包大小超出限制")
        seen = set()
        for item in z.infolist():
            name = item.filename.replace("\\", "/")
            path = Path(name)
            if PureWindowsPath(name).drive or path.is_absolute() or ".." in path.parts or ":" in name:
                raise ValueError("发行包包含不安全路径")
            relative = path.relative_to("WallpaperCompanion")
            if item.is_dir() or str(relative) == ".":
                continue
            if relative.as_posix() == "portable.flag":
                continue  # Preserve the user's marker; never change layout mode.
            if relative.parts[0] not in PROGRAM_ROOTS:
                raise ValueError("发行包含用户数据或非程序文件：" + str(relative))
            if relative.as_posix().casefold() in seen:
                raise ValueError("发行包路径重复")
            seen.add(relative.as_posix().casefold())
            entries.append((item, relative))
        if not {"WallpaperCompanion.exe", "USER_GUIDE.md"}.issubset({p.as_posix() for _, p in entries}):
            raise ValueError("发行包缺少 EXE 或使用手册")
        stage = checked_child(target, ".program-updates") / (match[1] + "-" + uuid.uuid4().hex[:8])
        payload = stage / "payload"
        payload.mkdir(parents=True)
        manifest = {}
        for item, relative in entries:
            output = checked_child(payload, relative)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(z.read(item))
            manifest[relative.as_posix()] = digest(output)
    plan = dict(version=match[1], target=str(target), files=manifest, archive_sha256=expected_sha256.lower())
    plan_path = stage / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path


def apply_update(plan_path, target):
    target, plan_path = writable_path(target), Path(plan_path).resolve()
    if not plan_path.is_relative_to(checked_child(target, ".program-updates").resolve()):
        raise ValueError("更新计划不在目标程序的暂存目录")
    if running_instances(target):
        raise RuntimeError("程序仍在运行。请先保存配置并从系统托盘退出；不会强制关闭。")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if Path(plan["target"]).resolve() != target:
        raise ValueError("更新计划的目标目录不匹配")
    payload = plan_path.parent / "payload"
    roots = set()
    for name, checksum in plan["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in PROGRAM_ROOTS:
            raise ValueError("更新清单包含非程序文件")
        path = checked_child(payload, relative)
        if digest(path) != checksum:
            raise ValueError("暂存程序校验失败：" + name)
        roots.add(relative.parts[0])
    before = personal_snapshot(target)
    backup = checked_child(target, ".program-backups") / (plan["version"] + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    completed = []
    try:
        # Replace complete library folders, and the EXE last; never merge DLL versions.
        for name in sorted(roots, key=lambda n: (n == "WallpaperCompanion.exe", n)):
            destination = checked_child(target, name)
            incoming = checked_child(payload, name)
            old = checked_child(backup, name)
            existed = destination.exists()
            if existed:
                destination.rename(old)
            completed.append((destination, incoming, old, existed))
            incoming.rename(destination)
        after = personal_snapshot(target)
        if before != after:
            raise RuntimeError("用户文件在更新期间发生变化，程序文件回退；请检查备份与当前配置")
    except Exception:
        for destination, incoming, old, existed in reversed(completed):
            if destination.exists():
                destination.rename(incoming)
            if existed and old.exists():
                old.rename(destination)
        raise
    result = dict(version=plan["version"], applied=True, personal_files_preserved=True,
                  protected_file_count=len(before), backup=str(backup))
    (backup / "update-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

