"""BGM toggle persistence, real playback and local/metadata artwork rendering."""
import json
from pathlib import Path
import sys
import tempfile
import wave
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QColor
from PySide6.QtMultimedia import QMediaMetaData
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from companion.core import ROOT, Store, new_profile
from companion.ui import Window
import shiboken6

app = QApplication([]); app.setQuitOnLastWindowClosed(False)
report = {}; output = ROOT / "output"; output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=output) as tmp, patch("companion.managed_api.api"):
    root = Path(tmp); music = root / "music"; music.mkdir()
    song = music / "测试.wav"
    with wave.open(str(song), "wb") as f:
        f.setparams((1, 2, 16000, 0, "NONE", "not compressed")); f.writeframes(b"\x01\x00" * 16000 * 10)
    store = Store(root / "data/config.json")
    p = new_profile("播放测试"); p.update(bgm_dir=str(music), desktop_only=False, fullscreen_mute=False, original_audio_policy="allow")
    store.config.update(profiles=[p], manual_profile=p["id"], we_dir="", workshop_dir=""); store.save()
    w = Window(store, hooks=False); w.show(); w.activate_profile(force=True); QTest.qWait(300)
    try:
        w.bgm_enabled.click(); QTest.qWait(40)
        report["toggle_off_hides_and_persists"] = not w.player_container.isVisible() and not Store(store.path).profile(p["id"])["bgm_enabled"] and not w.audio.bgm_allowed()
        w.tabs.setCurrentIndex(5)
        report["stays_hidden_on_other_pages"] = not w.player_container.isVisible()
        w.bgm_enabled.click(); QTest.qWait(120)
        report["toggle_on_restores_player"] = w.player_container.isVisible() and Store(store.path).profile(p["id"])["bgm_enabled"]
        with patch.object(w.audio, "set_profile", wraps=w.audio.set_profile) as reset_audio, patch.object(w.engine, "reset", wraps=w.engine.reset) as reset_rules:
            w.profile_name.setText("自动保存不重启音乐")
            assert w.autosave.flush()
            report["autosave_preserves_current_song_and_rule_clocks"] = not reset_audio.called and not reset_rules.called
        image = QImage(80, 80, QImage.Format.Format_RGB32); image.fill(QColor("#e19aab"))
        metadata = QMediaMetaData(); metadata.insert(QMediaMetaData.Key.CoverArtImage, image)
        with patch.object(w.audio.bgm, "metaData", return_value=metadata):
            w.refresh_album_art()
            report["embedded_metadata_art_rendered"] = not w.album_art.pixmap().isNull()
        image.save(str(music / "cover.png")); w.refresh_album_art()
        report["local_cover_fallback"] = not w.album_art.pixmap().isNull()
        (music / "cover.png").unlink(); w.refresh_album_art()
        report["no_art_uses_default"] = w.album_art.text() == "♫"
    finally:
        w.cleanup(); shiboken6.delete(w)
(output / "smoke-player-art.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report)); sys.exit(0 if all(report.values()) else 1)
