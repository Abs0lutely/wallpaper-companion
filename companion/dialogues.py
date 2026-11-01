"""Editable starter lines written for this project, not scraped game dialogue."""
from .i18n import tr
import copy
import uuid

CATEGORIES = ["点击回应", "返回桌面", "早晨", "白天", "夜间", "闲置陪伴"]
STARTER_LINES = {
    "点击回应": ["嗯？我在这里。", "有什么新发现吗？", "收到啦，继续陪你。", "别着急，我们慢慢来。", "今天也一起加油吧。", "休息一下再继续也可以。", "你一叫我，我就来啦。", "要不要换个心情，听首歌？"],
    "返回桌面": ["欢迎回来，今天也辛苦了。", "回来啦，刚好可以歇一会儿。", "事情处理得还顺利吗？", "桌面已经准备好，接下来做什么？", "又见面啦，继续一起忙吧。", "欢迎回来，先伸个懒腰吧。"],
    "早晨": ["早安，新的一天开始啦。", "早安，先给自己一点准备时间。", "早安，今天也一步一步来。", "早安，别忘了吃早餐。", "早安，希望今天有让你开心的小事。", "早安，我们从一件小事开始吧。"],
    "白天": ["下午好，记得喝点水。", "忙了一阵子，让眼睛休息一下吧。", "不必一次做完所有事，先完成眼前这一件。", "今天已经有一点进展了，继续就好。", "如果有点累，就换个姿势坐一会儿。", "窗外的光线不错，有空看看远处吧。"],
    "夜间": ["晚安，记得早点休息哦。", "夜深啦，今天就先到这里吧。", "晚安，剩下的事情明天再慢慢处理。", "忙完这一小段，就准备休息吧。", "晚安，愿你今晚睡个好觉。", "今天辛苦了，给自己留一点安静的时间。"],
    "闲置陪伴": ["安静待一会儿也很好。", "不用急着回应，我会在这里。", "要不要整理一下桌面，换个轻松的开始？", "听着音乐，慢慢做就好。", "偶尔放空一下，也算是在补充精神。", "等你准备好，我们再继续。"],
}


def starter_dialogues():
    return [dict(id="starter_" + str(index), category=category, text=text, enabled=True)
            for index, (category, text) in enumerate((c, t) for c, lines in STARTER_LINES.items() for t in lines)]


def normalize_dialogues(entries):
    if not isinstance(entries, list):
        raise ValueError(tr('ui.b2f4f27d3a7b', '台词库必须是列表'))
    result = []
    seen_ids = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            raise ValueError(tr('ui.0e4081250077', '每条台词需要 text 文本字段'))
        text = entry["text"].strip()
        if not text or len(text) > 4000:
            raise ValueError(tr('ui.220f7f0dffbf', '每条台词长度需要为 1–4000 字符'))
        category = str(entry.get("category", "闲置陪伴")).strip()
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        if (not category or len(category) > 60 or any(c in category for c in '/\\<>:"|?*')
                or any(ord(c) < 32 for c in category) or category.rstrip(" .") != category
                or category.split(".")[0].upper() in reserved):
            raise ValueError(tr('ui.9ffe37840476', '台词分类需要是有效的子目录名称'))
        identifier = str(entry.get("id", ""))
        if not identifier or identifier in seen_ids:
            identifier = uuid.uuid4().hex
        seen_ids.add(identifier)
        result.append(dict(id=identifier, category=category, text=text, enabled=bool(entry.get("enabled", True))))
    return result


def dialogue_rules():
    from .core import new_rule
    click = new_rule("key", "F8 · 点击回应")
    click["source"] = "点击回应"
    mouse = new_rule("mouse_middle", "鼠标中键 · 点击回应")
    mouse["source"] = "点击回应"
    welcome = new_rule("startup", "返回桌面问候 · 壁纸切入")
    welcome["source"] = "返回桌面"
    rules = [click, mouse, welcome]
    for category, start, end in [("早晨", "06:00", "11:00"), ("白天", "11:00", "22:00"), ("夜间", "22:00", "06:00")]:
        rule = new_rule("random", category + " · 随机陪伴")
        rule.update(source=category, start=start, end=end)
        rules.append(rule)
    return rules
