"""Exercise deferred views, snapshot invalidation and bounded model storage."""
import json
from pathlib import Path
import tempfile
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from companion.core import ROOT, Store, new_profile
from companion.ui import Window

app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(dir=ROOT / "output") as directory:
    root = Path(directory)
    voice = root / "voice"
    voice.mkdir()
    (voice / "a.wav").write_bytes(b"fixture")
    store = Store(root / "config.json")
    profile = new_profile("Deferred profile")
    profile.update(voice_dir=str(voice), bgm_dir="", use_bundled_demo=False)
    store.config.update(profiles=[profile], run_mode="standalone", standalone_profile=profile["id"])
    store.save()
    from companion.audio_index import IndexPending
    def indexed_files(index, folder):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                return index.files(folder)
            except IndexPending as pending:
                index.defer(pending, "test", lambda: None)
                app.processEvents()
                time.sleep(.01)
        raise AssertionError("Index did not become ready")
    w = Window(store, hooks=False)
    try:
        assert set(w._page_builders) == {2, 3, 4, 5, 6}
        assert w.active_id == profile["id"]
        assert w.autosave.flush()
        assert set(w._page_builders) == {2, 3, 4, 5, 6}
        assert len(indexed_files(w.audio_index, str(voice))) == 1
        (voice / "b.wav").write_bytes(b"fixture")
        w.audio_index.invalidate()
        assert len(indexed_files(w.audio_index, str(voice))) == 2
        (voice / "a.wav").unlink()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            app.processEvents()
            if [p.name for p in indexed_files(w.audio_index, str(voice))] == ["b.wav"]:
                break
            time.sleep(.01)
        else:
            raise AssertionError("External deletion was not reconciled")
        w.tabs.setCurrentIndex(6)
        deadline = time.monotonic() + 5
        while w.audio_library_busy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert not w.audio_library_busy and len(w.audio_records) == 1
        assert w.audio_table.rowCount() == 1
        assert w.page_pending(2) and w.page_pending(5)
        w.tabs.setCurrentIndex(5)
        assert len(w.edit_dialogues) == len(profile["dialogues"])
        w.skip_existing_dialogue_audio.setChecked(False)
        w.tabs.setCurrentIndex(2)
        assert not w.skip_existing_tts_audio.isChecked()
        w.skip_existing_tts_audio.setChecked(True)
        assert w.skip_existing_dialogue_audio.isChecked()
        assert w.autosave.flush()
        assert store.profile(profile["id"])["voice_dir"] == str(voice)
        from unittest.mock import patch
        from companion.core import new_rule
        rule = new_rule("random")
        rule.update(interval_min=300, interval_max=300, cooldown=0)
        store.profile(profile["id"])["rules"] = [rule]
        w.engine.next_due[rule["id"]] = -1
        w.audio_index.invalidate()
        played = []
        with patch.object(w.audio, "play_voice", side_effect=played.append):
            w.input_event("random", "")
            deadline = time.monotonic() + 5
            while not played and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
        assert len(played) == 1, "Cold index lost or duplicated a scheduled trigger"
        watched = [Path(path) for path in w.audio_index.watcher.directories()]
        assert all(path == voice or voice in path.parents for path in watched), watched
        w.cleanup()
        assert not w.audio_index.snapshots and not w.audio_index.watcher.directories()
        print(json.dumps({"deferred_runtime": True, "autosave_without_pages": True,
                          "external_changes": True, "first_navigation_refresh": True,
                          "cross_page_options": True, "cleanup": True}))
    finally:
        w.cleanup()
        w.close()
        app.processEvents()

    tray = Window(store, hooks=False, defer_editor=True)
    try:
        assert not tray._editor_ready and "logs" not in vars(tray)
        assert tray.active_id == profile["id"]
        tray.on_tick()
        tray.toggle_pause()
        assert tray.paused
        tray.show()
        app.processEvents()
        assert tray._editor_ready and tray.paused
        assert not tray.manual.isVisible() and not tray.navigation[4].isVisible()
        assert not tray.detect_button.isVisible()
        assert tray.active_id == profile["id"]
        assert tray.page_pending(2) and tray.page_pending(3)
    finally:
        tray.cleanup()
        tray.close()
        app.processEvents()
