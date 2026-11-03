"""Window-owned bounded audio snapshots with directory notifications and reconciliation."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal
from .core import audio_files, identity


class IndexPending(Exception):
    def __init__(self, key):
        self.key = key


class AudioIndex(QObject):
    ready = Signal(object, object, object)

    def __init__(self, parent=None, max_roots=16, max_files=50000):
        super().__init__(parent)
        self.max_roots, self.max_files = max_roots, max_files
        self.snapshots = OrderedDict()
        self.pending = {}
        self.callbacks = OrderedDict()
        self.transient = {}
        self.epoch = 0
        self.closed = False
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio-index")
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda _: self.invalidate())
        self.ready.connect(self._accept)
        self.timer = QTimer(self)
        self.timer.setInterval(10000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def files(self, folder, recursive=True):
        if not folder:
            return []
        key = (identity(str(Path(folder).expanduser().absolute())), recursive)
        if key in self.transient:
            return list(self.transient[key])
        if key in self.snapshots:
            self.snapshots.move_to_end(key)
            return list(self.snapshots[key])
        for (root, recurse), files in reversed(self.snapshots.items()):
            prefix = root.rstrip("/\\") + os.sep
            if recurse and key[0].startswith(prefix):
                return [path for path in files if identity(str(path)).startswith(key[0].rstrip("/\\") + os.sep)
                        and (recursive or identity(str(path.parent)) == key[0])]
        raise IndexPending(key)

    def defer(self, request, token, callback):
        if self.closed:
            return
        # A new request from the same playback/event consumer supersedes its old one.
        self.callbacks[token] = (request.key, callback)
        if len(self.callbacks) > 128:
            self.callbacks.popitem(last=False)
        self._submit(request.key)

    def _store(self, key, files):
        if self.closed or len(files) > self.max_files:
            return
        self.snapshots[key] = tuple(files)
        self.snapshots.move_to_end(key)
        while len(self.snapshots) > self.max_roots or sum(map(len, self.snapshots.values())) > self.max_files:
            self.snapshots.popitem(last=False)
        self._watch()

    def _watch(self):
        directories = set()
        for (root, _), files in self.snapshots.items():
            path = Path(root)
            while not path.is_dir() and path != path.parent:
                path = path.parent
            directories.add(str(path))
            for path in {file.parent for file in files}:
                while identity(str(path)) != root and path != path.parent:
                    directories.add(str(path))
                    path = path.parent
        wanted = set(sorted(directories)[:256])
        current = set(self.watcher.directories())
        if current - wanted:
            self.watcher.removePaths(list(current - wanted))
        if wanted - current:
            self.watcher.addPaths(list(wanted - current))

    def prewarm(self, folders):
        for folder in folders:
            if folder:
                key = (identity(str(Path(folder).expanduser().absolute())), True)
                if key not in self.snapshots:
                    self._submit(key)

    def _submit(self, key):
        if self.closed or key in self.pending or len(self.pending) >= self.max_roots:
            return
        epoch = self.epoch
        future = self.pool.submit(audio_files, *key)
        self.pending[key] = future
        def done(result):
            if not self.closed and not result.cancelled():
                try:
                    files = result.result()
                except Exception:
                    files = []
                try:
                    self.ready.emit((key, epoch), result, files)
                except RuntimeError:
                    pass  # QObject was destroyed after close().
        future.add_done_callback(done)

    def _accept(self, token, future, files):
        key, epoch = token
        if self.pending.get(key) is future:
            self.pending.pop(key)
        if not self.closed and epoch == self.epoch:
            self._store(key, files)
            self.transient[key] = tuple(files)
            try:
                callbacks = [(token, callback) for token, (requested, callback) in self.callbacks.items() if requested == key]
                for token, callback in callbacks:
                    self.callbacks.pop(token, None)
                    if not self.closed:
                        callback()
            finally:
                self.transient.pop(key, None)
            for requested, _ in list(self.callbacks.values()):
                self._submit(requested)

    def refresh(self):
        for key in list(self.snapshots):
            self._submit(key)

    def invalidate(self):
        keys = list(dict.fromkeys([*self.snapshots, *(key for key, _ in self.callbacks.values())]))
        self.epoch += 1
        self.snapshots.clear()
        for future in self.pending.values():
            future.cancel()
        self.pending.clear()
        for key in keys:
            self._submit(key)

    def close(self):
        self.closed = True
        self.timer.stop()
        if self.watcher.directories():
            self.watcher.removePaths(self.watcher.directories())
        self.snapshots.clear()
        self.pending.clear()
        self.callbacks.clear()
        self.transient.clear()
        self.pool.shutdown(wait=False, cancel_futures=True)
