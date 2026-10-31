import io
import json
import random
import tempfile
import threading
import unittest
import wave
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from companion.core import RuleEngine, Store, candidates, filename_for, new_profile, new_rule, save_generated, time_matches, writable_path
from companion.services import api_status, generate, local_url, selected_wallpaper

TEST_TEMP = Path(__file__).resolve().parents[1] / "output" / "test-temp"
TEST_TEMP.mkdir(parents=True, exist_ok=True)


def wav_bytes():
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 1600)
    return out.getvalue()


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEST_TEMP)
        self.root = Path(self.temp.name)
        self.profile = new_profile()
        self.profile["voice_dir"] = str(self.root)
        self.profile["global_cooldown"] = 3
        (self.root / "早安").mkdir()
        (self.root / "早安" / "早上好.wav").write_bytes(wav_bytes())
        (self.root / "欢迎回来.mp3").write_bytes(b"placeholder")
        (self.root / "ignore.txt").write_text("not audio")

    def tearDown(self):
        self.temp.cleanup()

    def test_day_and_midnight_windows(self):
        at = lambda h, m=0: datetime(2026, 10, 31, h, m)
        self.assertTrue(time_matches("00:00", "00:00", at(19)))
        self.assertTrue(time_matches("22:00", "06:00", at(23)))
        self.assertTrue(time_matches("22:00", "06:00", at(5, 59)))
        self.assertFalse(time_matches("22:00", "06:00", at(6)))
        self.assertFalse(time_matches("08:00", "10:00", at(10)))

    def test_sources_and_added_files(self):
        rule = new_rule()
        self.assertEqual(len(candidates(self.profile, rule)), 2)
        rule["source"] = "早安"
        self.assertEqual(candidates(self.profile, rule)[0].name, "早上好.wav")
        rule["keyword"] = "晚上"
        self.assertEqual(candidates(self.profile, rule), [])
        (self.root / "早安" / "晚上.wav").write_bytes(wav_bytes())
        self.assertEqual(len(candidates(self.profile, rule)), 1)
        rule["source"] = str(self.root / "欢迎回来.mp3")
        rule["keyword"] = ""
        self.assertEqual(len(candidates(self.profile, rule)), 1)

    def test_cooldown_and_correct_shortcut(self):
        engine = RuleEngine(random.Random(1))
        rule = self.profile["rules"][0]
        rule["cooldown"] = 10
        self.assertIsNone(engine.choose(self.profile, "key", now=0, hotkey="wrong"))
        self.assertIsNotNone(engine.choose(self.profile, "key", now=0, hotkey=rule["id"]))
        self.assertIsNone(engine.choose(self.profile, "key", now=9, hotkey=rule["id"]))
        self.assertIsNotNone(engine.choose(self.profile, "key", now=10, hotkey=rule["id"]))
        self.profile["enabled"] = False
        self.assertIsNone(engine.choose(self.profile, "key", now=30, hotkey=rule["id"]))

    def test_random_schedule_does_not_fire_immediately_and_resets(self):
        engine = RuleEngine(random.Random(1))
        rule = self.profile["rules"][1]
        rule.update(interval_min=5, interval_max=5, cooldown=0, start="08:00", end="09:00")
        morning = datetime(2026, 10, 31, 8, 30)
        noon = datetime(2026, 10, 31, 12)
        self.assertIsNone(engine.choose(self.profile, "random", now=0, clock=morning))
        self.assertIsNone(engine.choose(self.profile, "random", now=5, clock=noon))
        self.assertEqual(engine.next_due[rule["id"]], 10)
        self.assertIsNotNone(engine.choose(self.profile, "random", now=10, clock=morning))
        engine.reset()
        self.assertIsNone(engine.choose(self.profile, "random", now=100, clock=morning))

    def test_no_file_does_not_consume_global_cooldown(self):
        engine = RuleEngine()
        rule = self.profile["rules"][0]
        rule["keyword"] = "不存在"
        self.assertIsNone(engine.choose(self.profile, "key", now=0, hotkey=rule["id"]))
        rule["keyword"] = "欢迎"
        self.assertIsNotNone(engine.choose(self.profile, "key", now=0, hotkey=rule["id"]))

    def test_safe_filename_and_no_overwrite(self):
        text = '早安：你好吗？/\\*?'
        first = save_generated(self.root, text, wav_bytes())
        second = save_generated(self.root, text, wav_bytes())
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())
        self.assertNotIn("?", first.name)
        self.assertEqual(filename_for("CON"), "_CON.wav")
        self.assertLess(len(filename_for("台词" * 200)), 80)
        with self.assertRaises((wave.Error, EOFError)):
            save_generated(self.root, "失败", b"not wav")
        self.assertFalse((self.root / "失败.wav").exists())

    def test_protected_roots_and_config_roundtrip(self):
        for value in [self.root / "readonly" / "test.wav", self.root / "readonly" / "1" / "test.wav"]:
            with self.assertRaises(ValueError):
                writable_path(value, [self.root / "readonly"])
        with self.assertRaises(ValueError):
            save_generated(self.root / "readonly", "台词", wav_bytes(), [self.root])
        store = Store(self.root / "config.json")
        store.config["profiles"].append(self.profile)
        store.save()
        loaded = Store(store.path)
        self.assertEqual(loaded.profile(self.profile["id"])["voice_dir"], str(self.root))
        loaded.path.write_text("broken")
        with self.assertRaises(ValueError):
            Store(loaded.path)
        self.assertEqual(loaded.path.read_text(), "broken")

    def test_readonly_wallpaper_fallback_uses_selected_monitor_not_history(self):
        media = self.root / "wallpaper.mp4"
        media.write_bytes(b"fixture")
        (self.root / "project.json").write_text(json.dumps({"title": "当前壁纸"}), encoding="utf-8")
        data = {"fixture-user": {"general": {"wallpaperconfig": {"selectedwallpapers": {"Monitor1": {"file": str(media)}}},
                                          "wallpaperconfigrecent": [{"file": "wrong.mp4"}]}}}
        path = self.root / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        config = {"we_dir": str(self.root), "monitor": 1}
        before = path.read_bytes()
        result = selected_wallpaper(config)
        self.assertEqual(result["path"], str(media))
        self.assertEqual(result["title"], "当前壁纸")
        self.assertEqual(path.read_bytes(), before)
        config["monitor"] = 0
        self.assertEqual(selected_wallpaper(config)["path"], "")


class APIIntegrationTests(unittest.TestCase):
    def test_batch_http_payload_audio_validation_and_filename(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"paths":{"/tts":{}}}')
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(payload)
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.end_headers()
                self.wfile.write(wav_bytes())
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(dir=TEST_TEMP) as temp:
                root = Path(temp)
                reference = root / "ref.wav"
                reference.write_bytes(wav_bytes())
                settings = dict(url=f"http://127.0.0.1:{server.server_port}", reference=str(reference),
                                prompt="参考原文", text_lang="zh", prompt_lang="zh", speed=1.1)
                self.assertIn("就绪", api_status(settings))
                paths = generate(settings, ["欢迎回来", "早上好"], root / "out")
                self.assertEqual([Path(p).name for p in paths], ["欢迎回来.wav", "早上好.wav"])
                self.assertEqual(requests[0]["prompt_text"], "参考原文")
                self.assertFalse(requests[0]["streaming_mode"])
                self.assertTrue(all(Path(p).is_file() for p in paths))
        finally:
            server.shutdown()
            server.server_close()
        with self.assertRaises(ValueError):
            local_url("https://example.com")


if __name__ == "__main__":
    unittest.main()
