"""Read-only, relocatable factory samples; never seed or overwrite user directories."""
from .i18n import tr
import hashlib
import json
from pathlib import Path
from .core import ROOT


def bundled_root():
    return ROOT / "examples/audio"


def entry_file(root, entry):
    from .core import filename_for
    from .audio_names import matches_any_model
    name=entry.get("filename",filename_for(entry["text"]))
    if not isinstance(name,str) or Path(name).name!=name or Path(name).suffix.lower()!=".wav" or not matches_any_model(Path(name).stem,entry["text"]):
        raise ValueError(tr('ui.0bc08f39578f', '分发音频文件名不匹配台词，或包含目录路径'))
    return Path(root)/entry["category"]/name


def validate_starter_pack(root=None):
    root = Path(root) if root is not None else bundled_root()/"starter-voice"
    manifest = json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "wallpaper-companion-starter-audio" or manifest.get("version") != 1 or not manifest.get("files"):
        raise ValueError(tr('ui.746601ae0ed7', '随附示例语音清单无效'))
    from .core import filename_for
    from .dialogues import starter_dialogues
    known = {(e["category"],e["text"]) for e in starter_dialogues()}
    seen=set()
    for entry in manifest["files"]:
        key = entry["category"],entry["text"]
        file = entry_file(root,entry)
        relative = file.relative_to(root)
        if key not in known or key in seen or file.is_symlink() or not file.resolve().is_relative_to(root.resolve()):
            raise ValueError(tr('ui.13ff3129c062', '随附示例语音不在默认台词清单内或路径异常'))
        if hashlib.sha256(file.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(tr('ui.042885b84b5a', '随附示例语音校验不一致：')+str(relative))
        seen.add(key)
    return manifest


def validate_bundled_manifest(root=None):
    from .operation_pack import validate_wave
    from .action_lines import operation_dialogues
    from .dialogues import starter_dialogues
    from .core import filename_for
    root = Path(root) if root is not None else bundled_root()
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "wallpaper-companion-bundled-audio" or manifest.get("version") != 1:
        raise ValueError(tr('ui.302efe9880df', '分发音频总清单无效'))
    known={(pack,e["category"],e["text"]):Path(pack)/e["category"]/filename_for(e["text"])
           for pack,entries in [("starter-voice",starter_dialogues()),("operation-voice",operation_dialogues())] for e in entries}
    seen=set()
    for entry in manifest.get("files",[]):
        key=entry["pack"],entry["category"],entry["text"]
        if key not in known or key in seen:
            raise ValueError(tr('ui.aae9bf7a2284', '分发音频不在已知台词清单内或重复'))
        file=entry_file(root/entry["pack"],entry)
        if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest()!=entry["sha256"]:
            raise ValueError(tr('ui.c084e5523930', '分发音频哈希或路径校验失败'))
        validate_wave(file); seen.add(key)
    if not seen:
        raise ValueError(tr('ui.96df27be4e14', '分发音频清单为空'))
    actual={p.resolve() for p in root.rglob("*.wav")}
    listed={entry_file(root/e["pack"],e).resolve() for e in manifest["files"]}
    if actual != listed:
        raise ValueError(tr('ui.666857d95a29', '分发目录存在清单之外或缺失的音频'))
    return manifest
