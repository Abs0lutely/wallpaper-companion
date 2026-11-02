"""Switch shared dialogue files without overwriting the destination's contents."""
import copy
import json
import hashlib
from pathlib import Path
from .core import writable_path
from .dialogues import normalize_dialogues


def preview_binding(store,value,current):
    if not value.strip():return None,normalize_dialogues(current),None
    path=writable_path(value,store.protected())
    if path.suffix.lower()!=".json":raise ValueError("Dialogue library must be a JSON file")
    if path.exists():
        raw=path.read_bytes()
        if len(raw)>2*1024*1024:raise ValueError("Dialogue JSON exceeds 2 MiB")
        entries=normalize_dialogues(json.loads(raw.decode("utf-8-sig")))
        return path,entries,hashlib.sha256(raw).hexdigest()
    return path,normalize_dialogues(current),None


def switch_binding(store,profile_id,value,current,expected):
    before=copy.deepcopy(store.config)
    path,entries,stamp=preview_binding(store,value,current)
    if stamp!=expected:raise ValueError("Dialogue file changed after preview")
    created=False;written=None
    try:
        if path and not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True)
            written=json.dumps(entries,ensure_ascii=False,indent=2).encode("utf-8")
            with path.open("xb") as f:created=True;f.write(written)
        profile=store.profile(profile_id)
        if profile is None:raise ValueError("No profile selected")
        profile.update(dialogue_file=str(path) if path else "",dialogues=entries)
        store.save()
    except Exception:
        store.config=before
        if created and path.is_file() and path.read_bytes()==written:path.unlink()
        raise
    return profile
