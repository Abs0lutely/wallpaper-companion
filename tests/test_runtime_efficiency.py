import tempfile
import threading
import unittest
from pathlib import Path
from companion.core import audio_files
from companion.jobs import Jobs


class RuntimeEfficiencyTests(unittest.TestCase):
    def test_scandir_preserves_sorting_recursion_and_external_edits(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "nested").mkdir()
            for name in ("b.WAV", "A.mp3", "ignore.txt", "nested/c.ogg"):
                (root / name).write_bytes(b"fixture")
            self.assertEqual([p.name for p in audio_files(folder, False)], ["A.mp3", "b.WAV"])
            self.assertEqual(len(audio_files(folder)), 3)
            (root / "nested/c.ogg").unlink()
            (root / "nested/d.flac").write_bytes(b"fixture")
            self.assertEqual(audio_files(folder)[-1].name, "d.flac")

    def test_queries_progress_while_work_lane_is_full(self):
        jobs = Jobs()
        release = threading.Event()
        try:
            futures = [jobs.submit(lambda: release.wait(5)) for _ in range(32)]
            overflow = jobs.submit(lambda: "must not be queued")
            self.assertRaises(RuntimeError, overflow.result)
            self.assertEqual(jobs.submit(lambda: "ready", lane="query").result(timeout=1), "ready")
            self.assertFalse(futures[-1].done())
        finally:
            release.set()
            jobs.shutdown(wait=True)
        self.assertRaises(RuntimeError, jobs.submit(lambda: None).result)
