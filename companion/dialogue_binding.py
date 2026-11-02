"""Switch shared dialogue files without overwriting the destination's contents."""
import copy
import json
import hashlib
from pathlib import Path
from .core import writable_path
from .i18n import tr
from .dialogues import normalize_dialogues


def preview_binding(store,value,current):
    if not value.strip():return None,normalize_dialogues(current),None
    path=writable_path(value,store.protected())
    if path.suffix.lower()!=".json":raise ValueError(tr('binding.json_required','台词库必须为 JSON 文件。'))
    if path.exists():
        raw=path.read_bytes()
        if len(raw)>2*1024*1024:raise ValueError(tr('binding.too_large','台词 JSON 超过 2 MiB。'))
        entries=normalize_dialogues(json.loads(raw.decode("utf-8-sig")))
        return path,entries,hashlib.sha256(raw).hexdigest()
    return path,normalize_dialogues(current),None


def switch_binding(store,profile_id,value,current,expected):
    before=copy.deepcopy(store.config)
    path,entries,stamp=preview_binding(store,value,current)
    if stamp!=expected:raise ValueError(tr('binding.changed','预览后台词文件已改变，请重新选择并核对。'))
    created=False;written=None
    try:
        if path and not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True)
            written=json.dumps(entries,ensure_ascii=False,indent=2).encode("utf-8")
            with path.open("xb") as f:created=True;f.write(written)
        profile=store.profile(profile_id)
        if profile is None:raise ValueError(tr('binding.select','请先选择配置。'))
        profile.update(dialogue_file=str(path) if path else "",dialogues=entries)
        store.save()
    except Exception:
        store.config=before
        if created and path.is_file() and path.read_bytes()==written:path.unlink()
        raise
    return profile
