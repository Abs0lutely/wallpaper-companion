"""Program-only portable replacement, shared by CLI and frozen update helper."""
import hashlib
import json
import os
import re
import uuid
import zipfile
from pathlib import Path, PureWindowsPath
import psutil
from .paths import writable_path
from .update_text import ut

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
        raise ValueError(ut("unsafe_path", path=str(path)))
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
                raise RuntimeError(ut("unknown_process"))
            if Path(process.info["exe"]).resolve() == expected:
                found.append(process.pid)
        except psutil.NoSuchProcess:
            continue
    return found


def stage_update(archive, target, expected_sha256):
    archive, target = Path(archive).resolve(), writable_path(target)
    if not (target / "portable.flag").is_file() or not (target / "WallpaperCompanion.exe").is_file():
        raise ValueError(ut("not_portable"))
    if digest(archive) != expected_sha256.lower():
        raise ValueError(ut("checksum_failed"))
    match = re.fullmatch(r"WallpaperCompanion-(\d+\.\d+\.\d+)-windows-x64-portable\.zip", archive.name)
    if not match:
        raise ValueError(ut("package_name"))
    # Validate all archive entries before creating anything in the target.
    entries = []
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist()) > 20000 or sum(p.file_size for p in z.infolist()) > 2 * 1024**3:
            raise ValueError(ut("size_limit"))
        seen = set()
        for item in z.infolist():
            name = item.filename.replace("\\", "/")
            path = Path(name)
            if PureWindowsPath(name).drive or path.is_absolute() or ".." in path.parts or ":" in name:
                raise ValueError(ut("unsafe_archive"))
            relative = path.relative_to("WallpaperCompanion")
            if item.is_dir() or str(relative) == ".":
                continue
            if relative.as_posix() == "portable.flag":
                continue  # Preserve the user's marker; never change layout mode.
            if relative.parts[0] not in PROGRAM_ROOTS:
                raise ValueError(ut("non_program", path=str(relative)))
            if relative.as_posix().casefold() in seen:
                raise ValueError(ut("duplicate_path"))
            seen.add(relative.as_posix().casefold())
            entries.append((item, relative))
        if not {"WallpaperCompanion.exe", "USER_GUIDE.md"}.issubset({p.as_posix() for _, p in entries}):
            raise ValueError(ut("missing_program"))
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
        raise ValueError(ut("unsafe_plan"))
    if running_instances(target):
        raise RuntimeError(ut("instances"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if Path(plan["target"]).resolve() != target:
        raise ValueError(ut("wrong_target"))
    payload = plan_path.parent / "payload"
    roots = set()
    for name, checksum in plan["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in PROGRAM_ROOTS:
            raise ValueError(ut("unsafe_archive"))
        path = checked_child(payload, relative)
        if digest(path) != checksum:
            raise ValueError(ut("staged_changed", path=name))
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
            raise RuntimeError(ut("personal_changed"))
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
