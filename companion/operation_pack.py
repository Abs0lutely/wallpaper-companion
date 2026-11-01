"""Exact-manifest WAV validation for redistributable operation voice packs."""
import wave
from pathlib import Path
from .action_lines import operation_dialogues
from .core import filename_for


def validate_wave(path):
    path = Path(path)
    if path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("语音包文件过大：" + path.name)
    with wave.open(str(path),"rb") as sound:
        if sound.getnframes() < sound.getframerate()/10 or sound.getsampwidth()!=2:
            raise ValueError("语音包需要至少 0.1 秒的 16-bit PCM WAV：" + path.name)
        if not any(sound.readframes(sound.getnframes())):
            raise ValueError("语音包文件为静音：" + path.name)
        return dict(seconds=round(sound.getnframes()/sound.getframerate(),4),sample_rate=sound.getframerate(),channels=sound.getnchannels())


def validate_pack(root):
    root = Path(root).resolve()
    found, missing = [], []
    categories = set()
    for entry in operation_dialogues():
        relative = Path(entry["category"]) / filename_for(entry["text"])
        path = root / relative
        if not path.is_file():
            missing.append(relative.as_posix())
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 30 * 1024 * 1024:
            raise ValueError("语音包文件不安全或过大：" + str(relative))
        validate_wave(path)
        found.append(relative.as_posix())
        categories.add(entry["category"])
    expected = {entry["category"] for entry in operation_dialogues()}
    return dict(complete=not missing, ready=categories==expected, found=found, missing=missing, missing_categories=sorted(expected-categories))


def require_pack(root):
    result = validate_pack(root)
    if not result["ready"]:
        raise ValueError(f"默认操作语音未覆盖全部动作，缺 {len(result['missing_categories'])} 类。请先准备分发语音包；同类第二条为可选变体，不复制其他台词冒充。")
    return result
