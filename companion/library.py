"""Read-only library discovery and explicit bulk binding plans."""
from __future__ import annotations
from .i18n import tr

import copy
import json
import os
import uuid
from pathlib import Path

from .core import identity, new_profile, writable_path


def scan_wallpapers(config):
    roots = [config.get("workshop_dir", "")]
    if config.get("we_dir"):
        roots.append(str(Path(config["we_dir"]) / "projects/myprojects"))
    roots.extend(config.get("library_roots", []))
    records, warnings, visited = {}, [], set()
    for value in roots:
        if not value:
            continue
        root = Path(value).expanduser()
        if not root.is_dir():
            warnings.append(tr('ui.7c2aff9f5212', '扫描目录不存在：') + str(root))
            continue
        # Walk prunes once a project is found, without following directory links.
        def onerror(error):
            warnings.append(str(error))
        for directory, subdirs, files in os.walk(root, followlinks=False, onerror=onerror):
            subdirs[:] = [s for s in subdirs if s not in {".git", "node_modules", ".conda", ".venv"}]
            project_name = next((f for f in files if f.casefold() == "project.json"), None)
            if not project_name:
                continue
            subdirs[:] = []
            project = (Path(directory) / project_name).resolve()
            if identity(str(project)) in visited:
                continue
            visited.add(identity(str(project)))
            try:
                data = json.loads(project.read_text(encoding="utf-8-sig"))
                entry = data.get("file", "")
                if not isinstance(entry, str) or not entry:
                    raise ValueError(tr('ui.c53b931405fc', '缺少入口 file'))
                path = (project.parent / entry).resolve()
                if project.parent not in path.parents:
                    raise ValueError(tr('ui.87f1601cd978', '入口越出壁纸目录'))
                # Published scene projects usually name scene.json in metadata,
                # while WE ships that entry inside scene.pkg. No unpacking needed.
                if not path.is_file() and str(data.get("type", "")).casefold() == "scene" and path.suffix.casefold() == ".json":
                    packed = path.with_suffix(".pkg")
                    if packed.is_file():
                        path = packed
                if not path.is_file():
                    raise ValueError(tr('ui.a0279aa16cab', '入口不存在或越出壁纸目录'))
                record = dict(path=str(path), title=str(data.get("title") or project.parent.name),
                              type=str(data.get("type", tr('ui.4d8c1c5b4283', '未知'))), project=str(project),
                              workshop_id=project.parent.name if project.parent.name.isdigit() else "",
                              directory=str(project.parent), source=str(root))
                records[identity(str(path))] = record
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                warnings.append(str(project) + "：" + str(exc))
    return dict(records=sorted(records.values(), key=lambda r: (r["title"].casefold(), r["path"])), warnings=warnings)


def plan_bindings(config, records, *, mode="shared", voice_dir="", bgm_dir="", asset_dir="", template_id="", update_existing=False, data_root=None):
    from .core import DATA
    from .assets import load_dialogues, resource_paths
    if mode not in {"shared", "separate", "shared_root"}:
        raise ValueError(tr('ui.a1369110fc03', '未知绑定模式'))
    if not records:
        raise ValueError(tr('ui.dab41cc84cc5', '请先勾选壁纸'))
    updated = copy.deepcopy(config)
    protected = [p for p in [config.get("we_dir"), config.get("workshop_dir"), *config.get("library_roots", [])] if p]
    template = next((p for p in config["profiles"] if p["id"] == template_id), None)
    if template_id and template is None:
        raise ValueError(tr('ui.aa8843aa4416', '模板配置不存在'))
    if mode == "shared":
        for label, value in [(tr('ui.89fcbbfdca16', '语音'), voice_dir), ("BGM", bgm_dir)]:
            if value and not Path(value).is_dir():
                raise ValueError(label + tr('ui.85c016964ce0', '目录不存在'))
        if not voice_dir:
            raise ValueError(tr('ui.21cdbd30399b', '共享模式请选择语音目录'))
    created = changed = skipped = 0
    directories = []
    dialogue_files = {}
    seen = set()
    for record in records:
        key = identity(record["path"])
        if key in seen:
            continue
        seen.add(key)
        if not Path(record["path"]).is_file():
            raise ValueError(tr('ui.020c3a7616c7', '壁纸入口已失效，请重新扫描：') + record["path"])
        profile = next((p for p in updated["profiles"] if identity(p["wallpaper"]) == key), None)
        if profile and not update_existing:
            skipped += 1
            continue
        if profile:
            # Editing folder bindings never overwrites an existing profile's rules/name.
            changed += 1
        else:
            profile = copy.deepcopy(template) if template else new_profile()
            profile.update(id=uuid.uuid4().hex, name=record["title"], wallpaper=record["path"], private_asset_dir="")
            for rule in profile["rules"]:
                rule["id"] = uuid.uuid4().hex
            updated["profiles"].append(profile)
            created += 1
        if mode in {"separate", "shared_root"}:
            from .runtime import LAYOUT
            default_shared = Path(data_root) / "shared" if data_root else LAYOUT.shared_dir
            base = Path(asset_dir or config.get("shared_asset_dir") or default_shared) if mode == "shared_root" else Path(data_root or DATA) / "audio" / profile["id"]
            values = resource_paths(base, protected)
            entries = dialogue_files.get(values["dialogue_file"])
            if entries is None:
                entries = load_dialogues({**profile, **values})
                dialogue_files[values["dialogue_file"]] = entries
            profile.update(**values, dialogues=copy.deepcopy(entries))
            directories.extend([Path(values["voice_dir"]), Path(values["bgm_dir"])])
        else:
            profile.update(voice_dir=str(Path(voice_dir).resolve()), bgm_dir=str(Path(bgm_dir).resolve()) if bgm_dir else "")
    return dict(config=updated, directories=directories, dialogue_files=dialogue_files, created=created, updated=changed, skipped=skipped)


def apply_bindings(store, records, **options):
    from .assets import shared_root
    if options.get("mode") == "shared_root" and not options.get("asset_dir"):
        options["asset_dir"] = str(shared_root(store))
    plan = plan_bindings(store.config, records, data_root=store.path.parent, **options)
    # Validate every planned output before making any directory.
    for path in plan["directories"]:
        writable_path(path, store.protected())
    for path in plan["directories"]:
        path.mkdir(parents=True, exist_ok=True)
    from .assets import write_dialogues
    for path, entries in plan["dialogue_files"].items():
        if not Path(path).exists():
            write_dialogues(path, entries, store.protected())
    previous = store.config
    store.config = plan["config"]
    try:
        store.save()
    except Exception:
        store.config = previous
        raise
    return {key: plan[key] for key in ["created", "updated", "skipped"]}


def remove_profiles(store, profile_ids):
    """Delete configuration bindings only; never delete files or shared resources."""
    ids = set(profile_ids)
    previous = store.config
    updated = copy.deepcopy(previous)
    updated["profiles"] = [p for p in previous["profiles"] if p["id"] not in ids]
    count = len(previous["profiles"]) - len(updated["profiles"])
    if updated.get("manual_profile") in ids:
        updated["manual_profile"] = ""
    if updated.get("standalone_profile") in ids:updated["standalone_profile"]=""
    store.config = updated
    try:
        store.save()
    except Exception:
        store.config = previous
        raise
    return count
