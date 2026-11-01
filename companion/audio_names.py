"""Model-tagged names with backwards-compatible matching of legacy audio."""
from pathlib import Path, PureWindowsPath
import re
from .core import filename_for


def stems_with_copies(stems):
    return set(stems) | {re.sub(r" \(\d+\)$", "", stem) for stem in stems}


def has_audio(stems, text, model_name=None):
    accepted = {Path(filename_for(text)).stem.casefold(), Path(filename_for(text, model_name)).stem.casefold()}
    return bool(accepted & stems)


def matches_any_model(stem, text):
    candidates = stems_with_copies({stem.casefold()})
    if Path(filename_for(text)).stem.casefold() in candidates:
        return True
    for candidate in candidates:
        for split in (i for i,c in enumerate(candidate) if c == "-"):
            tag = candidate[split+1:]
            if tag and Path(filename_for(text,tag)).stem.casefold() == candidate:
                return True
    return False


def matching_files(folder, text):
    from .core import AUDIO_EXTENSIONS
    folder=Path(folder)
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and matches_any_model(p.stem,text)),key=lambda p:p.name.casefold()) if folder.is_dir() else []


def infer_model_label(settings, provider_id, character=None):
    if character:
        from .characters import project_file
        fields=("gpt_weights","sovits_weights")
        if any(settings.get(k) for k in fields):
            try:
                matched=all((not settings.get(k) and not character["settings"].get(k)) or project_file(settings,k)==project_file(character["settings"],k) for k in fields)
                if matched: return character["name"]
            except (ValueError,OSError): pass
    if provider_id == "gpt_sovits":
        for key in ("sovits_weights","gpt_weights"):
            if settings.get(key): return PureWindowsPath(str(settings[key])).stem
    values=[str(settings[k]).strip() for k in ("model","voice") if settings.get(k) is not None and str(settings.get(k,"")).strip()]
    return "-".join(values) or "未指定模型"
