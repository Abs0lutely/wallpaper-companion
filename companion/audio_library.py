"""Audio file inventory and guarded, non-overwriting file management."""
import shutil
from pathlib import Path, PureWindowsPath

from .assets import shared_root
from .core import AUDIO_EXTENSIONS, audio_files, identity, writable_path


def locations(store):
    root = shared_root(store)
    result = [dict(id="shared:" + kind, label="共享 · " + label, path=str(root / kind), profile="", kind=kind)
              for kind, label in [("voice", "语音"), ("bgm", "BGM")]]
    legacy = (store.path.parent / "audio/shared").resolve()
    if legacy != root and legacy.is_dir():
        for kind, label in [("voice", "语音"), ("bgm", "BGM")]:
            if (legacy / kind).is_dir():
                result.append(dict(id="legacy-shared:" + kind, scope="shared:" + kind,
                    label="旧共享目录 · " + label, path=str(legacy / kind), profile="", kind=kind))
    for profile in store.config["profiles"]:
        for kind, label in [("voice", "语音"), ("bgm", "BGM")]:
            path = profile.get(kind + "_dir", "")
            if path:
                result.append(dict(id=profile["id"] + ":" + kind, label=profile["name"] + " · " + label,
                                   path=path, profile=profile["id"], kind=kind))
    return result


def inventory(sources):
    records, cache, warnings = {}, {}, []
    for source in sources:
        folder = Path(source["path"]).expanduser().resolve()
        key = identity(str(folder))
        if key not in cache:
            if not folder.is_dir():
                warnings.append("目录尚未创建或无法访问：" + str(folder))
            cache[key] = audio_files(str(folder))
        for path in cache[key]:
            try:
                actual = path.resolve()
                item = records.setdefault(identity(str(actual)), dict(path=str(actual), name=path.name,
                    bytes=path.stat().st_size, locations=[], profiles=[], kinds=[], usages=[]))
                usage = dict(label=source["label"], directory=str(folder))
                if usage not in item["usages"]:
                    item["usages"].append(usage)
                for field, value in [("locations", source["label"]), ("profiles", source["profile"]), ("kinds", source["kind"])]:
                    if value and value not in item[field]:
                        item[field].append(value)
            except OSError as exc:
                warnings.append(str(exc))
    return dict(records=sorted(records.values(), key=lambda item: (item["name"].casefold(), item["path"])), warnings=warnings)


def destination(root, category="", protected=()):
    root = writable_path(root, protected)
    category = category.strip()
    relative = Path(category)
    if ":" in category or "\x00" in category or relative.is_absolute() or PureWindowsPath(category).drive or ".." in relative.parts or ".." in PureWindowsPath(category).parts:
        raise ValueError("分类子目录必须在目标音频目录内，不能填写绝对路径或上级目录")
    target = writable_path(root / relative, protected)
    if not target.is_relative_to(root):
        raise ValueError("分类目录不能通过链接指向目标目录之外")
    return target


def copy_audio(paths, target, protected=()):
    target = writable_path(target, protected)
    sources = [Path(path).resolve() for path in paths]
    if any(not p.is_file() or p.suffix.lower() not in AUDIO_EXTENSIONS for p in sources):
        raise ValueError("请选择已有的受支持音频文件")
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in sources:
        number = 1
        while True:
            name = source.name if number == 1 else f"{source.stem} ({number}){source.suffix}"
            output = writable_path(target / name, protected)
            if not output.is_relative_to(target):
                raise ValueError("目标文件不能通过链接指向音频目录之外")
            try:
                stream = output.open("xb")
                break
            except FileExistsError:
                number += 1
        try:
            with stream, source.open("rb") as original:
                shutil.copyfileobj(original, stream)
        except Exception as exc:
            output.unlink()  # Only the newly created partial copy, never an original.
            raise ValueError(f"复制失败；前 {len(copied)} 个副本已保留：{exc}") from exc
        copied.append(str(output))
    return copied


def recycle_audio(paths, protected=(), trash=None):
    if trash is None:
        from PySide6.QtCore import QFile
        trash = QFile.moveToTrash
    targets = list(dict.fromkeys(writable_path(path, protected) for path in paths))
    if any(not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS for path in targets):
        raise ValueError("只能将已存在的音频文件移入回收站")
    done = []
    for path in targets:
        result = trash(str(path))
        if not (result[0] if isinstance(result, tuple) else result):
            raise ValueError(f"无法移入回收站：{path.name}。已完成 {len(done)} 个；不会降级为永久删除。")
        done.append(str(path))
    return done
