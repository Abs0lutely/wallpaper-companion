"""Run UI regressions with one worktree-local environment and audited test data."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "output" / "ui-validation"
_RUN_TOKEN = os.environ.setdefault("WALLPAPER_COMPANION_VALIDATION_TOKEN", uuid.uuid4().hex)
DATA = VALIDATION / ("data-" + _RUN_TOKEN)
SMOKES = (
    "smoke_redesign.py", "smoke_ui.py", "smoke_controls.py",
    "smoke_polling_flicker.py", "smoke_library.py", "smoke_rules.py",
    "smoke_audio_library.py", "smoke_help.py", "smoke_resource_confirmation.py", "smoke_characters.py", "smoke_fresh_dialogues.py",
    "smoke_api_controls.py",
    "smoke_generation_feedback.py",
    "smoke_button_motion.py",
    "smoke_autosave.py",
    "smoke_player_art.py",
    "smoke_operation_voices.py",
    "smoke_duplicate_generation.py",
    "smoke_audio_scopes.py",
    "smoke_bundled_audio.py",
    "smoke_output_device.py",
    "smoke_i18n.py",
    "smoke_i18n_zh.py",
    "smoke_multilingual.py",
    "smoke_multilingual_en.py",
)


def configure():
    if Path.cwd().resolve() != ROOT or not Path(sys.executable).resolve().is_relative_to(ROOT / ".conda"):
        raise RuntimeError("Run from this worktree using its own .conda/python.exe.")
    DATA.mkdir(parents=True, exist_ok=True)
    temporary = VALIDATION / "temp"
    temporary.mkdir(exist_ok=True)
    os.environ.update(WALLPAPER_COMPANION_DATA=str(DATA), TEMP=str(temporary), TMP=str(temporary),
                      GPT_SOVITS_DIR="", PYTHONIOENCODING="utf-8")
    tempfile.tempdir = str(temporary)
    sys.path.insert(0, str(ROOT))


def worker(name):
    import requests
    from companion import paths
    with ExitStack() as stack:
        # Prevent discovery from reading the running WE instance or its libraries.
        stack.enter_context(patch.object(paths, "discover_wallpaper_engine", return_value=("", "")))
        from companion import core, services, runtime
        # Routine regressions use synthetic assets, never the shipped real voice clips.
        stack.enter_context(patch("companion.bundled_audio.bundled_root", return_value=VALIDATION/"empty-bundled-audio"))
        assert core.ROOT.resolve() == ROOT
        assert core.DATA.resolve() == DATA
        assert runtime.LAYOUT.plugin_dir.resolve().is_relative_to(ROOT)
        stack.enter_context(patch.object(core, "discover_wallpaper_engine", return_value=("", "")))
        stack.enter_context(patch.object(services, "running_wallpaper_processes", return_value=[]))

        original_init = core.Store.__init__
        original_save = core.Store.save
        audited = set()

        def audit(store):
            path = store.path.resolve()
            if not path.is_relative_to(ROOT / "output"):
                raise AssertionError(f"Test Store outside worktree output: {path}")
            audited.add(str(path))
            config = store.config
            values = [config.get(k, "") for k in ("we_dir", "workshop_dir", "shared_asset_dir")]
            values.extend(config.get("library_roots", []))
            for profile in config.get("profiles", []):
                values.extend(profile.get(k, "") for k in
                              ("voice_dir", "bgm_dir", "asset_dir", "private_asset_dir", "dialogue_file", "wallpaper"))
            for settings in [config.get("tts", {}), *config.get("tts_providers", {}).values(),
                             *(entry["settings"] for entry in config.get("tts_characters", []))]:
                values.extend(settings.get(k, "") for k in ("project", "reference", "python", "gpt_weights", "sovits_weights"))
            for value in values:
                if isinstance(value, str) and value:
                    candidate = Path(value).expanduser()
                    if candidate.exists() and not candidate.resolve().is_relative_to(ROOT):
                        raise AssertionError(f"Test resource outside worktree: {candidate}")

        def initialize(store, *args, **kwargs):
            original_init(store, *args, **kwargs)
            audit(store)

        def save(store):
            audit(store)
            return original_save(store)

        stack.enter_context(patch.object(core.Store, "__init__", initialize))
        stack.enter_context(patch.object(core.Store, "save", save))
        original_request = requests.Session.request

        def request(session, method, url, *args, **kwargs):
            target = urlparse(url)
            if target.hostname not in {"127.0.0.1", "localhost", "::1"} or target.port in {None, 9880}:
                raise AssertionError("UI validation only permits temporary loopback mock servers.")
            return original_request(session, method, url, *args, **kwargs)

        stack.enter_context(patch.object(requests.Session, "request", request))
        if name == "unit":
            suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
            result = unittest.TextTestRunner(verbosity=1).run(suite)
            passed = result.wasSuccessful()
        else:
            # GUI tests must never start or stop the actual local TTS service.
            stack.enter_context(patch("companion.managed_api.api"))
            stack.enter_context(patch("companion.ui.foreground_state", return_value=dict(desktop=True, fullscreen=False, own=False)))
            sys.argv = [str(ROOT / "tests" / name)]
            try:
                runpy.run_path(sys.argv[0], run_name="__main__")
                passed = True
            except SystemExit as exc:
                passed = exc.code in (None, 0)
        evidence = {"passed": passed, "python": sys.executable, "worktree": str(ROOT),
                    "data": str(DATA), "stores_audited": sorted(audited),
                    "discovery": "mocked", "network": "temporary loopback mocks only"}
        (VALIDATION / f"{name}.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("unit", *SMOKES))
    parser.add_argument("--only", choices=("unit", *SMOKES))
    args = parser.parse_args()
    configure()
    if args.worker:
        import faulthandler
        faulthandler.dump_traceback_later(60, exit=True)
        return worker(args.worker)
    jobs = [args.only] if args.only else ["unit", *SMOKES]
    results = {}
    for name in jobs:
        print(f"Validating {name}", flush=True)
        log = VALIDATION / f"{name}.log"
        with log.open("w", encoding="utf-8") as stream:
            try:
                code = subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()), "--worker", name],
                                      cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=70).returncode
            except subprocess.TimeoutExpired:
                code = 124
        results[name] = code
        print(f"{name}: {'PASS' if code == 0 else 'FAIL'}", flush=True)
        if code:
            print(log.read_text(encoding="utf-8")[-6000:], flush=True)
    summary = {"worktree": str(ROOT), "data": str(DATA), "results": results}
    (VALIDATION / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(code == 0 for code in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
