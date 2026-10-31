"""Rule validation and readable keyboard bindings shared by UI and preset import."""
import re
from datetime import datetime

BUILTIN_EVENTS = {"key", "any_key", "random", "scheduled", "startup", "mouse_left", "mouse_right", "mouse_middle", "mouse_x1", "mouse_x2", "scroll_up", "scroll_down"}


def valid_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError("时间需为 HH:mm")
    datetime.strptime(value, "%H:%M")
    return value


def validate_rule(rule):
    from pynput.keyboard import HotKey
    if not isinstance(rule.get("name"), str) or not 1 <= len(rule["name"].strip()) <= 100:
        raise ValueError("规则名称需要为 1–100 字符")
    event = rule.get("event", "")
    if not isinstance(event, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", event):
        raise ValueError("触发事件标识不合法")
    if not isinstance(rule.get("hotkey", ""), str) or len(rule.get("hotkey", "")) > 200:
        raise ValueError("按键配置必须是有效文字")
    if event == "key" and (not isinstance(rule.get("hotkey"), str) or not HotKey.parse(rule["hotkey"])):
        raise ValueError("请录制有效按键")
    for key in ["start", "end"]:
        valid_time(rule.get(key, "00:00"))
    if "at" in rule or event == "scheduled":
        valid_time(rule.get("at", "09:00"))
    for key, low, high in [("cooldown", 0, 86400), ("interval_min", 5, 86400), ("interval_max", 5, 86400)]:
        value = rule.get(key)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} 数值超出范围")
    if event == "random" and rule["interval_min"] > rule["interval_max"]:
        raise ValueError("最短间隔不能大于最长间隔")
    return rule


def display_hotkey(value):
    labels = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Win", "space": "空格", "enter": "Enter", "up": "↑", "down": "↓", "left": "←", "right": "→"}
    return " + ".join(labels.get(part.strip("<>"), part.strip("<>").upper()) for part in value.split("+"))


def qt_hotkey(event):
    """Convert one focused Qt key press into pynput's canonical HotKey notation."""
    from PySide6.QtCore import Qt
    key = event.key()
    if key in {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr}:
        return None
    names = {Qt.Key.Key_Space: "space", Qt.Key.Key_Return: "enter", Qt.Key.Key_Enter: "enter", Qt.Key.Key_Tab: "tab",
             Qt.Key.Key_Backspace: "backspace", Qt.Key.Key_Delete: "delete", Qt.Key.Key_Insert: "insert", Qt.Key.Key_Home: "home",
             Qt.Key.Key_End: "end", Qt.Key.Key_PageUp: "page_up", Qt.Key.Key_PageDown: "page_down", Qt.Key.Key_Up: "up",
             Qt.Key.Key_Down: "down", Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right", Qt.Key.Key_CapsLock: "caps_lock"}
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        token = f"<f{key - Qt.Key.Key_F1 + 1}>"
    elif key in names:
        token = "<" + names[key] + ">"
    elif 0x21 <= key <= 0x7e and chr(key) not in "+<>":
        token = chr(key).lower()
    else:
        raise ValueError("此键暂不支持，请使用字母、数字、功能键或常用控制键。")
    parts = []
    for mask, name in [(Qt.KeyboardModifier.ControlModifier, "ctrl"), (Qt.KeyboardModifier.AltModifier, "alt"),
                       (Qt.KeyboardModifier.ShiftModifier, "shift"), (Qt.KeyboardModifier.MetaModifier, "cmd")]:
        if event.modifiers() & mask:
            parts.append("<" + name + ">")
    return "+".join([*parts, token])
