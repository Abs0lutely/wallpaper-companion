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
    w = Window(store, hooks=False)
    try:
        assert set(w._page_builders) == {2, 3, 4, 5, 6}
        assert w.active_id == profile["id"]
        assert w.autosave.flush()
        assert set(w._page_builders) == {2, 3, 4, 5, 6}
        assert len(w.audio_index.files(str(voice))) == 1
        (voice / "b.wav").write_bytes(b"fixture")
        w.audio_index.invalidate()
        assert len(w.audio_index.files(str(voice))) == 2
        (voice / "a.wav").unlink()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            app.processEvents()
            if [p.name for p in w.audio_index.files(str(voice))] == ["b.wav"]:
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
        assert tray.active_id == profile["id"]
        assert tray.page_pending(2) and tray.page_pending(3)
    finally:
        tray.cleanup()
        tray.close()
        app.processEvents()
