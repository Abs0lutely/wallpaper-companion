import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree

from companion.core import defaults, ROOT
from companion.extensions import load_extensions
from companion.providers import builtin_providers, http_url
from test_core import wav_bytes, TEST_TEMP


class ProviderContractTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        recorded = self.requests
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                recorded.append((self.path, dict(self.headers), body))
                code = 401 if self.path == "/error" else 302 if self.path == "/redirect" else 200
                self.send_response(code)
                self.send_header("Location", "/should-not-follow")
                self.end_headers()
                self.wfile.write(b"sensitive-provider-error" if code != 200 else wav_bytes())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.providers = {p.id: p for p in builtin_providers()}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_azure_headers_and_escaped_ssml(self):
        p = self.providers["azure_speech"]
        text = '你好 <世界> & "朋友"'
        settings = dict(url=self.url + "/azure", api_key="fixture-secret", voice="zh-CN-XiaoxiaoNeural", locale="zh-CN", speed=1)
        self.assertEqual(p.synthesize(settings, text), wav_bytes())
        path, headers, body = self.requests[-1]
        self.assertEqual(headers["Ocp-Apim-Subscription-Key"], "fixture-secret")
        self.assertEqual(headers["X-Microsoft-OutputFormat"], "riff-24khz-16bit-mono-pcm")
        root = ElementTree.fromstring(body)
        self.assertEqual("".join(root.itertext()), text)

    def test_compatible_payload_and_remote_error_redaction(self):
        p = self.providers["openai_compatible"]
        settings = dict(url=self.url + "/speech", api_key="fixture-secret", model="vendor-model", voice="speaker", speed=1.1)
        self.assertEqual(p.synthesize(settings, "测试台词"), wav_bytes())
        path, headers, body = self.requests[-1]
        self.assertEqual(headers["Authorization"], "Bearer fixture-secret")
        payload = json.loads(body)
        self.assertEqual(payload["response_format"], "wav")
        self.assertEqual(payload["model"], "vendor-model")
        for endpoint in ["/error", "/redirect"]:
            settings["url"] = self.url + endpoint
            with self.assertRaises(ValueError) as error:
                p.synthesize(settings, "测试")
            self.assertNotIn("sensitive-provider-error", str(error.exception))
        self.assertEqual(len(self.requests), 3)

    def test_remote_http_is_rejected(self):
        with self.assertRaises(ValueError):
            http_url("http://example.com/tts")
        with self.assertRaises(ValueError):
            http_url("https://secret@example.com/tts")


class RegistryTests(unittest.TestCase):
    def test_optin_plugin_load_and_transactional_failure(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
            directory = Path(temp)
            (directory / "fixture.py").write_text('API_VERSION=1\ndef register(r):\n r.register_event("fixture_event", "Fixture", lambda config, now: True)\n', encoding="utf-8")
            config = defaults()
            registry = load_extensions(config, directory)
            self.assertNotIn("fixture_event", registry.events)
            config["enabled_plugins"] = ["fixture"]
            registry = load_extensions(config, directory)
            self.assertIn("fixture_event", registry.events)
            self.assertEqual(registry.loaded, ["fixture"])
            (directory / "broken.py").write_text('API_VERSION=1\ndef register(r):\n r.register_event("partial", "Partial")\n raise ValueError("failed")\n', encoding="utf-8")
            config["enabled_plugins"] = ["broken", "../outside"]
            registry = load_extensions(config, directory)
            self.assertNotIn("partial", registry.events)
            self.assertEqual(len(registry.errors), 2)
            self.assertIn("qt", registry.audio)
            self.assertIn("pynput", registry.inputs)
            self.assertIn("wallpaper_engine", registry.wallpapers)

    def test_examples_are_loadable_extensions(self):
        config = defaults()
        config["enabled_plugins"] = ["hourly_chime", "custom_http_tts"]
        registry = load_extensions(config, ROOT / "examples/plugins")
        self.assertEqual(registry.errors, [])
        self.assertIn("hourly_chime", registry.events)
        self.assertIn("custom_http_tts", registry.speech)


if __name__ == "__main__":
    unittest.main()
