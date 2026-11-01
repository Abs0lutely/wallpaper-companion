"""Exercise real Qt endpoint changes without changing Windows defaults."""
import json
from pathlib import Path
import sys
import tempfile
import time
import wave
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtMultimedia import QAudioDevice, QMediaDevices, QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from companion.audio import Audio
from companion.core import ROOT, new_profile


def wait(predicate):
    end = time.monotonic() + 6
    while not predicate() and time.monotonic() < end:
        QTest.qWait(20)
        time.sleep(.002)
    assert predicate()


app = QApplication([])
audio = Audio()
report = {}
devices = QMediaDevices.audioOutputs()
default = QMediaDevices.defaultAudioOutput()
assert not default.isNull(), "This native playback test requires an output device."
other = next((device for device in devices if device.id() != default.id()), None)
with tempfile.TemporaryDirectory(dir=ROOT / "output") as directory:
    path = Path(directory) / "test.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000 * 20)
    profile = new_profile("Output routing test")
    profile.update(bgm_dir=directory, voice_volume=7, bgm_volume=9)
    audio.set_profile(profile)
    audio.play_voice(path)
    wait(lambda: audio.voice.position() > 300 and audio.bgm.position() > 300)
    report["initial_default"] = all(output.device().id() == default.id()
                                   for output in (audio.voice_output, audio.bgm_output))
    if other is not None:
        volumes = (audio.voice_output.volume(), audio.bgm_output.volume())
        source = (audio.voice.source(), audio.bgm.source())
        positions = (audio.voice.position(), audio.bgm.position())
        # Simulate default-device notifications, but route only our disposable
        # players to real hardware. Do not change the user's Windows setting.
        with patch("companion.audio.QMediaDevices.defaultAudioOutput", return_value=other):
            audio.media_devices.audioOutputsChanged.emit()
            wait(lambda: all(output.device().id() == other.id()
                             for output in (audio.voice_output, audio.bgm_output)))
            wait(lambda: audio.voice.position() > positions[0] and audio.bgm.position() > positions[1])
            report["live_switch_preserves_playback"] = (
                source == (audio.voice.source(), audio.bgm.source()) and
                volumes == (audio.voice_output.volume(), audio.bgm_output.volume()) and
                audio.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
            audio.set_bgm_paused(True)
        audio.media_devices.audioOutputsChanged.emit()
        report["return_to_default_preserves_pause"] = (
            all(output.device().id() == default.id() for output in (audio.voice_output, audio.bgm_output))
            and audio.bgm_paused and audio.bgm.playbackState() == QMediaPlayer.PlaybackState.PausedState)
        with patch("companion.audio.QMediaDevices.defaultAudioOutput", return_value=QAudioDevice()):
            audio.media_devices.audioOutputsChanged.emit()
            report["temporary_no_device"] = audio.voice_output.device().id() == default.id()
        # Starting playback also repairs a stale output even without a signal.
        audio.voice_output.setDevice(other)
        audio.bgm_output.setDevice(other)
        audio.play_voice(path)
        report["play_rechecks_default"] = all(output.device().id() == default.id()
                                             for output in (audio.voice_output, audio.bgm_output))
        wait(lambda: audio.voice.position() > 100)
    else:
        report["cross_device_test"] = "NOT TESTED: only one available output"
    audio.stop()
    audio.deleteLater()
    app.processEvents()
assert all(value is not False for value in report.values()), report
(ROOT / "output" / "smoke-output-device.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
