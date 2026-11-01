"""Portable UI-operation rules, independent of wallpaper interaction rules."""
import math
from .action_lines import EVENT_LINES
from .dialogues import normalize_dialogues

FORMAT = "wallpaper-companion-operation-rules"


def default_rules():
    return [dict(event=event, enabled=True, category=category, cooldown=1.2)
            for event, (category, _) in EVENT_LINES.items()]


def normalize_rules(rules):
    if not isinstance(rules, list) or len(rules) > len(EVENT_LINES):
        raise ValueError("操作回应规则必须是已知动作列表")
    result = {r["event"]: r for r in default_rules()}
    seen = set()
    for r in rules:
        if not isinstance(r, dict) or r.get("event") not in EVENT_LINES or r["event"] in seen:
            raise ValueError("操作动作未知或重复")
        if not isinstance(r.get("enabled"), bool):
            raise ValueError("规则启用值必须是布尔值")
        cooldown = r.get("cooldown", 1.2)
        if isinstance(cooldown, bool) or not isinstance(cooldown, (int, float)) or not math.isfinite(cooldown) or not 0 <= cooldown <= 3600:
            raise ValueError("规则冷却需在 0–3600 秒之间")
        if not isinstance(r.get("category"), str):
            raise ValueError("播放分类必须是文本")
        category = normalize_dialogues([dict(text="分类校验", category=r["category"])])[0]["category"]
        seen.add(r["event"])
        result[r["event"]] = dict(event=r["event"],enabled=r["enabled"],category=category,cooldown=float(cooldown))
    return list(result.values())


def normalize_payload(value):
    if not isinstance(value, dict) or value.get("format") != FORMAT or value.get("version") != 1:
        raise ValueError("不是支持的操作回应规则文件")
    gap = value.get("min_interval", 1.2)
    if isinstance(gap, bool) or not isinstance(gap,(int,float)) or not math.isfinite(gap) or not .25 <= gap <= 60:
        raise ValueError("操作回应最短间隔需在 0.25–60 秒之间")
    if not isinstance(value.get("enabled", True), bool):
        raise ValueError("操作回应总开关必须是布尔值")
    return dict(format=FORMAT, version=1, enabled=value.get("enabled", True), min_interval=float(gap), rules=normalize_rules(value.get("rules", [])))


def config_payload(config):
    return normalize_payload(dict(format=FORMAT,version=1,enabled=config.get("operation_voice_enabled",True),
        min_interval=config.get("operation_voice_min_interval",1.2),rules=config.get("operation_voice_rules",default_rules())))
