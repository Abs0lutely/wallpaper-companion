"""Opt-in packaged smoke test. Uses disposable data; never calls a TTS service."""
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import traceback
import wave
from pathlib import Path


def run(destination):
    from PySide6.QtCore import QTimer
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtWidgets import QApplication
    import keyring
    import shiboken6
    from .core import DATA, ROOT, Store, new_profile, writable_path
    from .extensions import load_extensions
    from .presets import export_payload, import_payload
    from .runtime import LAYOUT
    from .services import InputHooks
    from .startup import startup_command
    from .external import run_external
    from .ui import Window, STYLE

    target = writable_path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    report = {"frozen": bool(getattr(sys, "frozen", False)), "portable": LAYOUT.portable,
              "app_dir": str(ROOT), "data_dir": str(DATA), "checks": {}, "media_errors": []}
    checks = report["checks"]
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    fixture = tempfile.TemporaryDirectory(dir=target.parent)
    window = None
    hooks = None
    code = 1
    try:
        root = Path(fixture.name)
        from .assets import shared_root, load_dialogues
        checks["default_shared_location"] = shared_root(Store()) == LAYOUT.shared_dir
        fresh_store = Store(root / "fresh/config.json")
        fresh = Window(fresh_store, hooks=False)
        try:
            checks["fresh_install_shows_default_dialogues_without_binding"] = not fresh.editing_id and fresh.dialogue_table.rowCount() == 38
            fresh.edit_dialogues = []
            fresh.render_dialogues()
            fresh.add_starter_dialogues()
            checks["fresh_install_supplement_and_save_work"] = fresh.save_dialogue_library() and len(load_dialogues(dict(dialogue_file=str(shared_root(fresh_store) / "dialogues.json")))) == 38
        finally:
            fresh.cleanup()
            shiboken6.delete(fresh)
        for name in ["voice", "bgm"]:
            (root / name).mkdir()
            with wave.open(str(root / name / "测试语音.wav"), "wb") as wav:
                wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                wav.writeframes(b"".join(struct.pack("<h", int(100 * math.sin(i * math.tau * 440 / 16000)))
                                        for i in range(16000 * 10)))
        store = Store(root / "config.json")
        profile = new_profile("打包自检")
        profile.update(voice_dir=str(root / "voice"), bgm_dir=str(root / "bgm"),
                       desktop_only=False, fullscreen_mute=False, original_audio_policy="allow")
        store.config.update(profiles=[profile], manual_profile=profile["id"])
        store.save()
        window = Window(store, hooks=False)
        from .core import save_generated
        named = save_generated(root / "naming", "命名检查", (root / "voice/测试语音.wav").read_bytes(), store.protected(), model_name="测试模型")
        checks["model_tagged_filename_and_control"] = named.name == "命名检查-测试模型.wav" and named.is_file() and window.filename_model.maxLength() == 200
        window.poll.stop()
        window.show()
        from PySide6.QtCore import QSize
        checks["shared_brand_icon_available"] = (ROOT / "readme-assets/app-icon.ico").is_file() and {QSize(16,16), QSize(32,32), QSize(48,48), QSize(256,256)}.issubset(set(window.windowIcon().availableSizes())) and window.windowIcon().pixmap(32,32).toImage() == window.tray.icon().pixmap(32,32).toImage()
        checks["redesigned_navigation_present"] = {0, 2, 3, 4, 5, 6, 7}.issubset(window.navigation)
        checks["character_model_controls_present"] = window.provider_widgets["gpt_weights"].isEditable() and window.provider_widgets["sovits_weights"].isEditable()
        from .managed_api import api
        checks["manual_api_controls_present"] = window.start_api_button.text() == "启动本地 API" and window.check_api_button.isEnabled() and not api.owns_service()
        window.tts_busy = True
        window.begin_generation(2)
        window.generation_update(dict(completed=1, total=2, message="打包自检：已保存一条（无合成调用）"))
        window.finish_generation_progress(False, "自检结束；没有调用语音服务")
        window.tts_busy = False
        checks["generation_progress_preserves_partial_result"] = window.tts_progress.value() == 1 and window.tts_progress.maximum() == 2 and "已保存一条" in window.tts_stage_output.toPlainText()
        from .motion import ButtonScaleEffect
        checks["button_motion_and_feedback_loaded"] = isinstance(window.start_api_button.graphicsEffect(), ButtonScaleEffect) and bool(window.action_feedback.buttons)
        checks["autosave_and_operation_controls_present"] = hasattr(window, "autosave") and window.operation_voice_enabled.isChecked() and not window.selected_dialogues()
        from .operation_pack import require_pack
        if report["frozen"]:
            checks["distributed_operation_voice_actions_covered"] = require_pack(ROOT / "examples/audio/operation-voice")["ready"]
            from .bundled_audio import validate_starter_pack, validate_bundled_manifest
            checks["distributed_starter_voice_pack_verified"] = bool(validate_starter_pack()["files"])
            checks["distributed_default_audio_hashes_verified"] = bool(validate_bundled_manifest()["files"])
        store.config["operation_voice_enabled"] = False  # Keep the remaining diagnostics' audio deterministic.
        from .sovits_config import model_key
        checks["model_config_dependency_available"] = model_key({}) is None
        window.audio.message.connect(lambda s: report["media_errors"].append(s) if "失败" in s else None)
        checks["manual_and_examples_present"] = all((ROOT / name).exists() for name in
                                                   ["USER_GUIDE.md", "README.md", "examples/interaction-preset.json", "readme-assets/home.png",
                                                    "readme-assets/dialogues.png", "readme-assets/rules.png", "examples/dialogues/heartfelt-zh-CN.json"])
        checks["internal_manual_opens"] = window.open_document("USER_GUIDE.md") and "功能和输入框使用手册" in window.document_viewer.browser.toPlainText()
        from PySide6.QtCore import QUrl
        window.document_viewer.follow_link(QUrl("BUILDING.md"))
        checks["internal_manual_navigation"] = window.document_viewer.current_path == ROOT / "BUILDING.md"
        window.document_viewer.close()
        checks["keyring_windows_backend"] = "Windows" in type(keyring.get_keyring()).__module__
        registry = load_extensions({**store.config, "enabled_plugins": ["hourly_chime", "custom_http_tts"]}, ROOT / "examples/plugins")
        checks["external_examples_load"] = len(registry.loaded) == 2 and not registry.errors
        checks["all_builtin_tts_providers"] = {"gpt_sovits", "azure_speech", "openai_compatible"}.issubset(registry.speech)
        exported, _ = export_payload([profile])
        other = Store(root / "imported/config.json")
        imported = import_payload(other, exported)
        checks["preset_roundtrip"] = len(imported["profile_ids"]) == 1
        checks["frozen_startup_command"] = not report["frozen"] or "main.py" not in startup_command()
        child = run_external([str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe"), "/d", "/c", "echo external-ready"],
                             capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        checks["external_process_launch"] = child.returncode == 0 and b"external-ready" in child.stdout
        hooks = InputHooks(lambda *args: None)
        hooks.start()

        def finish():
            try:
                checks["voice_plays"] = window.audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                checks["bgm_ducked"] = abs(window.audio.bgm_output.volume() - .25 * .25) < .01
                window.toggle_pause()
                checks["pause_stops_audio"] = not window.audio.busy and window.audio.bgm.playbackState() != QMediaPlayer.PlaybackState.PlayingState
                window.profile_name.setText("打包自检已保存")
                checks["save_from_ui"] = window.save_profile() and Store(store.path).config["profiles"][0]["name"] == "打包自检已保存"
                saved = Store(store.path).config
                checks["appearance_and_character_settings_persist"] = "appearance" in saved and saved["tts_characters"] == []
                checks["input_listeners_alive"] = hooks.keyboard_listener.is_alive() and hooks.mouse_listener.is_alive()
                checks["window_screenshot"] = window.grab().save(str(target.with_suffix(".png")))
            except Exception:
                report["error"] = traceback.format_exc()
            finally:
                app.exit(0 if all(checks.values()) and not report["media_errors"] and "error" not in report else 1)

        def initial():
            checks["profile_activated"] = window.active_id == profile["id"]
            checks["bgm_plays"] = window.audio.bgm.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            window.preview_voice()
            QTimer.singleShot(1200, finish)

        QTimer.singleShot(2500, initial)
        QTimer.singleShot(20000, lambda: (report.update(error="self-test timeout"), app.exit(2)))
        code = app.exec()
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if hooks:
            hooks.stop()
        if window:
            window.cleanup()
            shiboken6.delete(window)
            app.processEvents()
        fixture.cleanup()
        report["passed"] = code == 0 and bool(checks) and all(checks.values()) and not report["media_errors"] and "error" not in report
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1
