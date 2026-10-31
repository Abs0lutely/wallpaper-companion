import io
import json
import tempfile
import threading
import time
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from companion.managed_api import LocalAPI
from companion.services import api_status, generate_dialogue_entries
from companion.core import filename_for


class ModelLoadingTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in ("a.ckpt", "a.pth", "b.ckpt", "b.pth", "reference.wav"):
            (root / name).write_bytes(b"fixture")
        state = dict(models={}, switches=[], posts=[], fail_gpt=False)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path.startswith("/set_"):
                    kind = "gpt" if parsed.path == "/set_gpt_weights" else "sovits"
                    weight = parse_qs(parsed.query)["weights_path"][0]
                    state["switches"].append((kind, weight))
                    if kind == "gpt" and state["fail_gpt"]:
                        self.send_response(400); self.end_headers(); self.wfile.write(b'{"message":"failure"}'); return
                    state["models"][kind] = weight
                    time.sleep(.01)
                    self.send_response(200); self.end_headers(); self.wfile.write(b'{"message":"success"}')
                else:
                    self.send_response(200); self.end_headers(); self.wfile.write(b'{"paths":{"/tts":{}}}')
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                state["posts"].append((payload, state["models"].copy()))
                audio = io.BytesIO()
                with wave.open(audio, "wb") as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b"\0\0" * 160)
                self.send_response(200); self.end_headers(); self.wfile.write(audio.getvalue())
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        api = LocalAPI(root / "appdata")
        self.addCleanup(api.shutdown)
        settings = dict(project=str(root), url=f"http://127.0.0.1:{server.server_port}", gpt_weights="a.ckpt",
            sovits_weights="a.pth", reference="reference.wav", prompt="原文", text_lang="zh", prompt_lang="zh")
        return root, api, settings, state

    def test_external_models_are_not_changed_without_explicit_permission(self):
        root, api, settings, state = self.fixture()
        for permission in (None, False, "false", "true", 1):
            with self.subTest(permission=permission):
                with self.assertRaisesRegex(ValueError, "其他软件"):
                    api.synthesize({**settings, "allow_external_model_switch": permission}, "test")
        self.assertEqual(state["switches"], [])
        self.assertEqual(state["posts"], [])
        api.shutdown()
        self.assertIn("就绪", api_status(settings))

    def test_models_load_before_audio_once_per_external_batch(self):
        root, api, settings, state = self.fixture()
        settings.update(allow_external_model_switch=True, _tts_batch_id="batch-a")
        self.assertTrue(api.synthesize(settings, "one").startswith(b"RIFF"))
        api.synthesize(settings, "two")
        self.assertEqual([kind for kind, _ in state["switches"]], ["sovits", "gpt"])
        self.assertEqual(state["posts"][0][0]["ref_audio_path"], str((root / "reference.wav").resolve()))
        self.assertEqual(state["posts"][0][1]["gpt"], str((root / "a.ckpt").resolve()))
        api.synthesize({**settings, "_tts_batch_id": "batch-b"}, "three")
        self.assertEqual(len(state["switches"]), 4)

    def test_load_failure_never_synthesizes_with_half_switched_models(self):
        _, api, settings, state = self.fixture()
        settings.update(allow_external_model_switch=True)
        state["fail_gpt"] = True
        with self.assertRaisesRegex(ValueError, "模型加载失败"):
            api.synthesize(settings, "never")
        self.assertEqual(state["posts"], [])
        self.assertIsNone(api.loaded_models)
        state["fail_gpt"] = False
        api.synthesize(settings, "retry")
        self.assertEqual(len(state["posts"]), 1)

    def test_concurrent_requests_keep_model_selection_and_audio_atomic(self):
        root, api, settings, state = self.fixture()
        settings.update(allow_external_model_switch=True)
        errors = []
        def run(character):
            try:
                api.synthesize({**settings, "gpt_weights": character + ".ckpt", "sovits_weights": character + ".pth"}, character)
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=run, args=(name,)) for name in ("a", "b")]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertEqual(errors, [])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(state["posts"]), 2)
        for payload, models in state["posts"]:
            self.assertEqual(models["gpt"], str((root / (payload["text"] + ".ckpt")).resolve()))
            self.assertEqual(models["sovits"], str((root / (payload["text"] + ".pth")).resolve()))

    def test_invalid_selection_and_all_skipped_entries_do_not_start_api(self):
        root, api, settings, state = self.fixture()
        with patch.object(api, "ensure") as ensure:
            with self.assertRaises(ValueError):
                api.synthesize({**settings, "sovits_weights": ""}, "no")
            ensure.assert_not_called()
        folder = root / "voice/早安"; folder.mkdir(parents=True)
        (folder / filename_for("早上好")).write_bytes(b"already here")
        with patch("companion.managed_api.api", api), patch.object(api, "synthesize") as synthesize:
            result = generate_dialogue_entries(settings, [dict(text="早上好", category="早安", enabled=True)], root / "voice")
            self.assertEqual(result["skipped"], 1)
            synthesize.assert_not_called()
