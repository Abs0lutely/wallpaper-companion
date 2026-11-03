from __future__ import annotations
from .i18n import tr

import random
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

from .core import audio_files


class Audio(QObject):
    message = Signal(str)
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.index = parent.audio_index if parent is not None and hasattr(parent, "audio_index") else None
        self.scan = self.index.files if self.index else audio_files
        self.voice_output = QAudioOutput(self)
        self.bgm_output = QAudioOutput(self)
        self.voice = QMediaPlayer(self)
        self.bgm = QMediaPlayer(self)
        self.voice.setAudioOutput(self.voice_output)
        self.bgm.setAudioOutput(self.bgm_output)
        # QAudioOutput can retain the endpoint chosen when it was created.
        # Keep the monitor alive, including while the window is in the tray.
        self.media_devices = QMediaDevices(self)
        self.media_devices.audioOutputsChanged.connect(self.sync_output_device)
        self.sync_output_device()
        self.profile = None
        self.profile_epoch = 0
        self.paused = False
        self.bgm_paused = False
        self.bgm_blocked = False
        self.files = []
        self.failed = set()
        self.last_bgm = None
        self.voice.playbackStateChanged.connect(self._voice_state)
        self.voice.errorOccurred.connect(lambda error, text: self.message.emit(tr('ui.ecaa76ff966a', '语音播放失败：') + text))
        self.bgm.errorOccurred.connect(self._bgm_error)
        self.bgm.mediaStatusChanged.connect(self._bgm_status)

    @property
    def busy(self):
        return self.voice.playbackState() == QMediaPlayer.PlaybackState.PlayingState or self.voice.mediaStatus() == QMediaPlayer.MediaStatus.LoadingMedia

    def sync_output_device(self):
        device = QMediaDevices.defaultAudioOutput()
        # With no endpoint (e.g. during Bluetooth reconnection), wait for the
        # next notification. Do not restart players or change pause/volume.
        if device.isNull():
            return
        for output in (self.voice_output, self.bgm_output):
            if output.device().id() != device.id():
                output.setDevice(device)

    def set_profile(self, profile):
        self.profile_epoch += 1
        self.stop()
        self.profile = profile
        self.bgm_paused = bool(profile and profile.get("bgm_paused", False))
        self.failed.clear()
        self.files = []
        self.last_bgm = None
        self.set_volumes()
        if self.bgm_allowed():
            self.next_bgm()

    def bgm_allowed(self):
        return bool(self.profile and self.profile.get("enabled", True) and self.profile.get("bgm_enabled", True)
                    and not self.paused and not self.bgm_paused and not self.bgm_blocked)

    def sync_bgm(self):
        self.sync_output_device()
        if not self.bgm_allowed():
            self.bgm.pause()
        elif self.bgm.source().isEmpty() or self.bgm.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_bgm()
        else:
            self.bgm.play()
        self.changed.emit()

    def set_bgm_paused(self, paused):
        self.bgm_paused = bool(paused)
        self.sync_bgm()

    def set_bgm_blocked(self, blocked):
        self.bgm_blocked = bool(blocked)
        self.sync_bgm()

    def set_volumes(self):
        p = self.profile or {}
        self.voice_output.setVolume(p.get("voice_volume", 80) / 100)
        duck = p.get("duck_percent", 25) / 100 if self.busy else 1
        self.bgm_output.setVolume(p.get("bgm_volume", 25) / 100 * duck)

    def play_voice(self, path):
        self.sync_output_device()
        self.voice.stop()
        self.voice.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
        self.voice.play()
        self.message.emit(tr('ui.ef22c9aee39c', '语音：') + Path(path).stem)

    def _voice_state(self, state):
        self.set_volumes()
        self.changed.emit()

    def next_bgm(self):
        if not self.bgm_allowed():
            return
        self.sync_output_device()
        from .audio_index import IndexPending
        try:
            self.files = self.scan(self.profile.get("bgm_dir", ""))
        except IndexPending as pending:
            epoch = self.profile_epoch
            self.index.defer(pending, "bgm", lambda: self.next_bgm() if self.profile_epoch == epoch else None)
            return
        available = [p for p in self.files if str(p) not in self.failed]
        if not available:
            self.bgm.stop()
            return
        if self.profile.get("bgm_shuffle", True):
            options = [p for p in available if p != self.last_bgm] or available
            track = random.choice(options)
        else:
            index = available.index(self.last_bgm) + 1 if self.last_bgm in available else 0
            track = available[index % len(available)]
        self.last_bgm = track
        self.bgm.setSource(QUrl.fromLocalFile(str(track.resolve())))
        self.bgm.play()
        self.message.emit("BGM：" + track.name)
        self.changed.emit()

    def _bgm_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            QTimer.singleShot(0, self.next_bgm)

    def _bgm_error(self, error, text):
        if self.last_bgm:
            self.failed.add(str(self.last_bgm))
        self.message.emit(tr('ui.7e509393a425', 'BGM 播放失败，跳过此文件：') + text)
        QTimer.singleShot(200, self.next_bgm)

    def set_paused(self, paused):
        if self.paused == paused:
            return
        self.paused = paused
        if paused:
            self.voice.stop()
            self.bgm.pause()
        else:
            self.sync_bgm()
        self.changed.emit()

    def stop(self):
        self.voice.stop()
        self.voice.setSource(QUrl())
        self.bgm.stop()
        self.bgm.setSource(QUrl())
        self.changed.emit()
