import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil
from companion.managed_api import LocalAPI
from companion.services import api_status, generate


class ManagedAPITests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        # Reserve a free port, then let the child bind it.
        with ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as server:
            port = server.server_port
        script = root / "api_v2.py"
        script.write_text('''import argparse, json, subprocess, sys, io, wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('-a'); p.add_argument('-p',type=int); a=p.parse_args()
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])
Path('child.pid').write_text(str(child.pid))
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  self.send_response(200); self.end_headers(); self.wfile.write(b'{"paths":{"/tts":{}}}')
 def do_POST(self):
  self.rfile.read(int(self.headers['Content-Length']))
  data=io.BytesIO()
  with wave.open(data,'wb') as f:
   f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000); f.writeframes(b'\\x00\\x00'*160)
  self.send_response(200); self.end_headers(); self.wfile.write(data.getvalue())
HTTPServer((a.a,a.p),Handler).serve_forever()
''', encoding="utf-8")
        settings = dict(project=str(root), python=sys.executable, url=f"http://127.0.0.1:{port}",
                        reference=str(root / "ref.wav"), prompt="参考原文")
        (root / "ref.wav").write_bytes(b"fixture")
        api = LocalAPI(root / "data")
        self.addCleanup(api.shutdown)
        return root, settings, api

    def test_generation_lazily_starts_api_then_shutdown_reaps_tree(self):
        root, settings, api = self.fixture()
        self.assertIsNone(api.process)
        with patch("companion.managed_api.api", api):
            files = generate(settings, ["测试台词"], root / "voice")
        self.assertTrue(Path(files[0]).is_file())
        process = api.process
        child = psutil.Process(int((root / "child.pid").read_text()))
        api.ensure(settings)
        self.assertIs(api.process, process)
        api.shutdown()
        self.assertIsNotNone(process.poll())
        self.assertFalse(child.is_running())
        with self.assertRaisesRegex(RuntimeError, "退出"):
            api.ensure(settings)

    def test_external_api_reused_and_never_terminated(self):
        root, settings, owner = self.fixture()
        owner.ensure(settings)
        guest = LocalAPI(root / "guest")
        with patch("companion.managed_api.popen_external") as launch:
            guest.ensure(settings)
            guest.shutdown()
            launch.assert_not_called()
        self.assertIsNone(guest.process)
        self.assertIn("就绪", api_status(settings))

    def test_shutdown_during_loading_prevents_restart(self):
        root, settings, api = self.fixture()
        errors = []
        # Child starts, but health checks simulate model loading until shutdown.
        import requests
        def worker():
            try:
                api.ensure(settings)
            except Exception as exc:
                errors.append(exc)
        with patch("companion.services.api_status", side_effect=requests.ConnectionError):
            thread = threading.Thread(target=worker)
            thread.start()
            deadline = time.monotonic() + 5
            while api.process is None and time.monotonic() < deadline:
                time.sleep(.01)
            process = api.process
            self.assertIsNotNone(process)
            api.shutdown()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertIsNotNone(process.poll())
        self.assertTrue(errors)

    def test_cancel_before_generation_creates_no_process_or_file(self):
        root, settings, api = self.fixture()
        cancel = threading.Event(); cancel.set()
        with patch("companion.managed_api.api", api):
            with self.assertRaisesRegex(ValueError, "取消"):
                generate(settings, ["取消"], root / "voice", cancel=cancel)
        self.assertIsNone(api.process)
        self.assertFalse((root / "voice").exists())

    def test_protected_log_directory_prevents_launch(self):
        root, settings, api = self.fixture()
        with patch("companion.managed_api.popen_external") as launch:
            with self.assertRaises(ValueError):
                api.ensure(settings, [api.data_dir])
            launch.assert_not_called()
        self.assertIsNone(api.process)
