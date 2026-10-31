"""Verify native Windows listener receives an otherwise unused F24 key event."""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from companion.services import InputHooks
from companion.core import ROOT, new_rule
from pynput import keyboard

received = []
ready = threading.Event()
def callback(event, rule):
    received.append((event, rule))
    if event == "key":
        ready.set()
rule = new_rule()
rule["hotkey"] = "<f24>"
hooks = InputHooks(callback)
hooks.configure([rule])
try:
    hooks.start()
    hooks.keyboard_listener.wait()
    hooks.mouse_listener.wait()
    alive = hooks.keyboard_listener.is_alive() and hooks.mouse_listener.is_alive()
    controller = keyboard.Controller()
    controller.press(keyboard.Key.f24)
    controller.release(keyboard.Key.f24)
    matched = ready.wait(3)
    assert alive and matched, (alive, matched, received)
    report = dict(keyboard_and_mouse_listeners_alive=alive, native_shortcut_received=matched, events=received)
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    (output / "hooks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
finally:
    hooks.stop()
