"""Prepare private api_v2 inference configs without changing the AI project."""
import copy
import uuid
from pathlib import Path
import yaml

from .characters import project_file, version_hint
from .core import writable_path


def model_key(settings):
    values = [str(settings.get(key, "")).strip() for key in ("gpt_weights", "sovits_weights")]
    if not any(values):
        return None
    if not all(values):
        raise ValueError("请同时选择 GPT 和 SoVITS 模型；或同时留空沿用当前模型")
    result = []
    for key, suffix in (("gpt_weights", ".ckpt"), ("sovits_weights", ".pth")):
        path = project_file(settings, key)
        if not path.is_file() or path.suffix.lower() != suffix or path.stat().st_size == 0:
            raise ValueError("模型不存在、为空或格式错误：" + key)
        stat = path.stat()
        result.append((str(path), stat.st_size, stat.st_mtime_ns))
    return tuple(result)


def runtime_config(settings, data_dir, protected=()):
    selected = model_key(settings)
    project = Path(settings.get("project", "")).expanduser().resolve()
    source = project / "GPT_SoVITS/configs/tts_infer.yaml"
    if not source.is_file() and selected is None:
        return None
    if not source.is_file() or source.stat().st_size > 2_000_000:
        raise ValueError("未找到有效的 GPT_SoVITS/configs/tts_infer.yaml，无法准备所选模型的推理配置")
    config = yaml.safe_load(source.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("GPT-SoVITS 推理配置不是有效字典")
    saved_custom = config.get("custom") or {}
    if not isinstance(saved_custom, dict):
        raise ValueError("GPT-SoVITS custom 推理配置格式错误")
    version = version_hint(settings.get("sovits_weights", "")) or saved_custom.get("version", "v2")
    custom = config.get("custom", config.get(version, config.get("v2", {})))
    if not isinstance(custom, dict):
        raise ValueError("GPT-SoVITS custom 推理配置格式错误")
    config = copy.deepcopy(config)
    config["custom"] = {**custom, "version": version}
    if selected:
        config["custom"].update(t2s_weights_path=selected[0][0], vits_weights_path=selected[1][0])
    path = writable_path(Path(data_dir) / "tts-runtime" / (uuid.uuid4().hex + ".yaml"), protected)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, allow_unicode=False, sort_keys=False), encoding="utf-8")
    return path
