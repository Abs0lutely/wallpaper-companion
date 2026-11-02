"""Stable language-specific resource categories; never moves user files."""
import copy
import json
from functools import lru_cache
from pathlib import Path

LOCALES = ("zh-CN", "ja-JP", "en-US")


@lru_cache(maxsize=4)
def translated_lines(pack, locale):
    from .core import ROOT
    if locale not in {"ja-JP", "en-US"} or pack not in {"starter", "operation"}:
        return []
    return json.loads((ROOT / f"examples/dialogues/{pack}-{locale}.json").read_text(encoding="utf-8-sig"))


def category_for(base, locale):
    for suffix in ("·ja-JP", "·en-US"):
        base = base.removesuffix(suffix)
    return base if locale == "zh-CN" else base + "·" + locale


def switch_operation_categories(rules, locale):
    from .action_lines import EVENT_LINES
    if locale not in LOCALES:
        raise ValueError("Invalid voice locale")
    result=copy.deepcopy(rules); changed=0
    for rule in result:
        base=EVENT_LINES[rule["event"]][0]
        if rule["category"] in {category_for(base,l) for l in LOCALES}:
            target=category_for(base,locale)
            changed += rule["category"] != target
            rule["category"]=target
    return result,changed


def migrate_categories(entries):
    result=copy.deepcopy(entries); changes=[]
    known=[e for locale in ("ja-JP","en-US") for pack in ("starter","operation") for e in translated_lines(pack,locale)]
    by_id={e["id"]:e for e in known}
    for entry in result:
        match=by_id.get(entry.get("id"))
        if match and (match["text"]!=entry["text"] or entry["category"]!=match["category"].rsplit("·",1)[0]):match=None
        if not match:match=next((e for e in known if e["text"]==entry["text"] and entry["category"]==e["category"].rsplit("·",1)[0]),None)
        if match:
            changes.append((entry["category"],match["category"],entry["text"]))
            entry["category"]=match["category"]
    return result,changes


def legacy_candidates(voice_root, category):
    from .core import audio_files
    from .audio_names import matches_any_model
    if not voice_root:
        return []
    locale=next((l for l in ("ja-JP","en-US") if category.endswith("·"+l)),None)
    if not locale:
        return []
    entries=[e for pack in ("starter","operation") for e in translated_lines(pack,locale) if e["category"]==category]
    if not entries:
        return []
    return [p for p in audio_files(str(Path(voice_root)/category.rsplit("·",1)[0])) if any(matches_any_model(p.stem,e["text"]) for e in entries)]
