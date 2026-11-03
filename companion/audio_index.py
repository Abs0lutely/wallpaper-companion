"""Window-owned bounded audio snapshots with directory notifications and reconciliation."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal
from .core import audio_files, identity


class AudioIndex(QObject):
    ready = Signal(object, object, object)

    def __init__(self, parent=None, max_roots=16, max_files=50000):
        super().__init__(parent)
        self.max_roots, self.max_files = max_roots, max_files
        self.snapshots = OrderedDict()
        self.pending = {}
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
        if key in self.snapshots:
            self.snapshots.move_to_end(key)
            return list(self.snapshots[key])
        # Preserve first-trigger semantics on a cold directory. Subsequent reads
        # use snapshots; active roots are prewarmed and reconciled in a worker.
        files = audio_files(folder, recursive)
        self._store(key, files)
        return list(files)

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
            for file in files:
                path = file.parent
                while str(path) != root and path != path.parent:
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
                self.ready.emit((key, epoch), future, files)
        future.add_done_callback(done)

    def _accept(self, token, future, files):
        key, epoch = token
        if self.pending.get(key) is future:
            self.pending.pop(key)
        if not self.closed and epoch == self.epoch:
            self._store(key, files)

    def refresh(self):
        for key in list(self.snapshots):
            self._submit(key)

    def invalidate(self):
        keys = list(self.snapshots)
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
        self.pool.shutdown(wait=False, cancel_futures=True)
