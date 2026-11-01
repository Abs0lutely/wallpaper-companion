"""Exact-manifest WAV validation for redistributable operation voice packs."""
import wave
from pathlib import Path
from .action_lines import operation_dialogues
from .core import filename_for


def validate_pack(root):
    root = Path(root).resolve()
    found, missing = [], []
    for entry in operation_dialogues():
        relative = Path(entry["category"]) / filename_for(entry["text"])
        path = root / relative
        if not path.is_file():
            missing.append(relative.as_posix())
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 30 * 1024 * 1024:
            raise ValueError("语音包文件不安全或过大：" + str(relative))
        with wave.open(str(path), "rb") as sound:
            if sound.getnframes() < sound.getframerate() / 10 or sound.getsampwidth() != 2:
                raise ValueError("语音包需要至少 0.1 秒的 16-bit PCM WAV：" + str(relative))
            if not any(sound.readframes(sound.getnframes())):
                raise ValueError("语音包文件为静音：" + str(relative))
        found.append(relative.as_posix())
    return dict(complete=not missing, found=found, missing=missing)


def require_pack(root):
    result = validate_pack(root)
    if not result["complete"]:
        raise ValueError(f"默认操作语音未齐备，还缺 {len(result['missing'])} 条。请先按 examples/dialogues/operation-zh-CN.json 生成并准备分发语音包；不发布缺少首次体验音频的版本。")
    return result
