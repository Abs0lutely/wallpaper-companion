import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path

from companion.updates import (API_URL, REPOSITORY, ReleaseClient, UpdateCancelled,
                               check_due, parse_release, read_state, write_state)
from companion.core import Store
from test_core import TEST_TEMP


def release_payload(data=b"installer", version="0.12.0", portable=False):
    suffix = "portable.zip" if portable else "setup.exe"
    name = f"WallpaperCompanion-{version}-windows-x64-{suffix}"
    url = f"https://github.com/{REPOSITORY}/releases/"
    return dict(tag_name="v" + version, html_url=url + "tag/v" + version,
                body="Release notes", draft=False, prerelease=False, assets=[
                    dict(name=name, size=len(data), browser_download_url=url + "download/v" + version + "/" + name,
                         digest="sha256:" + hashlib.sha256(data).hexdigest()),
                    dict(name="SHA256SUMS.txt", browser_download_url=url + "download/v" + version + "/SHA256SUMS.txt")])


class Response:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, size):
        for i in range(0, len(self.body), 3): yield self.body[i:i + 3]


class Session:
    def __init__(self, responses): self.responses = responses; self.headers = {}
    def get(self, url, **kwargs):
        body = self.responses[url]
        if isinstance(body, Exception): raise body
        return Response(body)


class ReleaseTests(unittest.TestCase):
    def test_newer_stable_and_matching_layout_only(self):
        for portable in (False, True):
            p = release_payload(portable=portable)
            r = parse_release(p, "0.11.0", portable)
            self.assertEqual(r.version, "0.12.0")
            self.assertTrue(r.name.endswith("portable.zip" if portable else "setup.exe"))
            self.assertIsNone(parse_release(p, "0.12.0", portable))
            self.assertIsNone(parse_release(p, "0.13.0", portable))
            for flag in ("draft", "prerelease"):
                self.assertIsNone(parse_release({**p, flag: True}, "0.11.0", portable))

    def test_invalid_tag_missing_or_untrusted_asset_rejected(self):
        for change in (dict(tag_name="v0.12.0-rc1"), dict(assets=[]), dict(html_url="https://example.com/bad")):
            with self.assertRaises(ValueError): parse_release({**release_payload(), **change}, "0.11.0", False)
        p = release_payload(); p["assets"][0]["browser_download_url"] = "https://github.com/other/project/releases/download/v0.12.0/bad.exe"
        with self.assertRaises(ValueError): parse_release(p, "0.11.0", False)

    def client(self, data=b"installer", sums=None):
        p = release_payload(data)
        r = parse_release(p, "0.11.0", False)
        sums = (hashlib.sha256(data).hexdigest() + "  " + r.name).encode() if sums is None else sums
        return ReleaseClient(Session({API_URL: json.dumps(p).encode(), r.checksum_url: sums, r.url: data})), r

    def test_download_verified_before_becoming_ready(self):
        client, r = self.client()
        cancel = threading.Event()
        self.assertEqual(client.latest("0.11.0", False, cancel), r)
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            progress = []
            path, checksum = client.download(r, tmp, cancel, lambda n, size: progress.append((n, size)))
            self.assertEqual(path.read_bytes(), b"installer")
            self.assertEqual(checksum, hashlib.sha256(b"installer").hexdigest())
            self.assertEqual(progress[-1], (9, 9))
            self.assertFalse(list(Path(tmp).glob("*.part")))

    def test_missing_mismatched_duplicate_checksums_never_install(self):
        client, r = self.client()
        valid = (hashlib.sha256(b"installer").hexdigest() + "  " + r.name).encode()
        for sums in (b"", b"0" * 64 + b"  " + r.name.encode(), valid + b"\n" + valid):
            client, r = self.client(sums=sums)
            with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
                with self.assertRaises(ValueError): client.download(r, tmp, threading.Event())
                self.assertFalse(list(Path(tmp).iterdir()))

    def test_cancel_and_wrong_size_remove_partial_file(self):
        client, r = self.client()
        for cancel_after_start in (False, True):
            cancel = threading.Event()
            if not cancel_after_start: cancel.set()
            with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
                with self.assertRaises(UpdateCancelled):
                    client.download(r, tmp, cancel, lambda n, size: cancel.set())
                self.assertFalse(list(Path(tmp).glob("*.part")))
                self.assertFalse((Path(tmp) / r.name).exists())
        client, r = self.client(); client.session.responses[r.url] = b"truncated"
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            with self.assertRaises(ValueError): client.download(r, tmp, threading.Event())
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_check_cadence_and_state_tolerate_bad_file(self):
        self.assertTrue(check_due({}, 100))
        self.assertFalse(check_due({"last_check": 50}, 100))
        self.assertTrue(check_due({"last_check": 200}, 100))
        self.assertTrue(check_due({"last_check": "bad"}, 100))
        self.assertTrue(check_due({"last_check": 50}, 90000))
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            path = Path(tmp) / "update-state.json"
            self.assertEqual(read_state(path), {})
            write_state(path, {"last_check": 42})
            self.assertEqual(read_state(path), {"last_check": 42})
            path.write_text("broken")
            self.assertEqual(read_state(path), {})

    def test_existing_config_defaults_on_and_keeps_explicit_opt_out(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as tmp:
            path = Path(tmp) / "config.json"
            for values, expected in (({}, True), ({"auto_update_enabled": False}, False), ({"auto_update_enabled": "false"}, True)):
                path.write_text(json.dumps({"profiles": [], "monitor": 3, **values}))
                store = Store(path)
                self.assertIs(store.config["auto_update_enabled"], expected)
                self.assertEqual(store.config["monitor"], 3)
