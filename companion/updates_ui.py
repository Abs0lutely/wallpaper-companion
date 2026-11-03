"""Nonblocking update controller; only explicit user confirmation hands off an install."""
import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path

import psutil
from PySide6.QtCore import QObject, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout

from .core import writable_path
from .i18n import language
from .runtime import LAYOUT
from .update_helper import atomic_json, launch_environment
from .update_text import ut
from .updates import Release, ReleaseClient, UpdateCancelled, check_due, current_version, read_state, write_state


class UpdateController(QObject):
    event = Signal(object, str, object)

    def __init__(self, window, *, layout=LAYOUT, client_factory=ReleaseClient):
        super().__init__(window)
        self.w = window
        self.layout = layout
        self.client_factory = client_factory
        self.root = writable_path(window.store.path.parent / "updates", window.store.protected())
        self.state_path = self.root / "state.json"
        self.state = read_state(self.state_path)
        self.version = current_version(layout.app_dir)
        self.cancel = None
        self.closed = False
        self.manual = False
        self.release = None
        self.download = None
        self.repair = False
        self.dialog = None
        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self.automatic_check)
        self.event.connect(self.receive)
        self.sync()
        QTimer.singleShot(10_000, self.automatic_check)
        QTimer.singleShot(1000, self.previous_result)

    def sync(self):
        enabled = self.w.store.config.get("auto_update_enabled", True)
        if enabled and not self.closed:
            self.timer.start()
        else:
            self.timer.stop()
            if self.cancel and not self.manual:
                self.cancel.set()
                self.status(ut("cancelled"))

    def preference_changed(self):
        if self.w.autosave.flush():
            self.sync()
        else:
            self.w.auto_update_enabled.blockSignals(True)
            self.w.auto_update_enabled.setChecked(self.w.store.config.get("auto_update_enabled", True))
            self.w.auto_update_enabled.blockSignals(False)
            self.sync()

    def status(self, message):
        self.w.update_status.setText(message)

    def automatic_check(self):
        if not self.closed and not self.repair and self.w.store.config.get("auto_update_enabled", True) and check_due(self.state):
            self.check(manual=False)

    def check(self, manual=True):
        if self.closed:
            return
        if manual and not self.w.autosave.flush():
            return
        if self.cancel is not None:
            if manual:
                self.manual = True
                self.show_dialog()
            return
        # Reuse only files verified during this process; helper verifies them again.
        if manual and self.release and self.download:
            self.show_dialog()
            return
        self.manual = manual
        cancel = self.cancel = threading.Event()
        self.status(ut("checking"))
        if manual:
            self.show_dialog()

        def emit(kind, value):
            if not self.closed:
                try:
                    self.event.emit(cancel, kind, value)
                except RuntimeError:
                    pass

        def work():
            try:
                client = self.client_factory()
                release = client.latest(self.version, self.layout.portable, cancel)
                emit("release", release)
                if release and self.layout.frozen:
                    folder = writable_path(self.root / ("download-" + release.version), self.w.store.protected())
                    last = [0.0]
                    def progress(done, total):
                        now = time.monotonic()
                        if now - last[0] >= 0.15 or done == total:
                            last[0] = now
                            emit("progress", (release.version, int(done * 100 / total)))
                    package, checksum = client.download(release, folder, cancel, progress)
                    emit("download", (package, checksum))
                emit("done", None)
            except UpdateCancelled:
                emit("cancelled", None)
            except Exception as exc:
                emit("error", str(exc))
        threading.Thread(target=work, name="companion-update", daemon=True).start()

    def receive(self, token, kind, value):
        if self.closed or token is not self.cancel:
            return
        if token.is_set() and kind not in {"cancelled", "error", "done"}:
            return
        if kind == "release":
            self.release = value
            self.download = None
            self.repair = False
            self.state["last_check"] = time.time()
            try:
                write_state(self.state_path, self.state)
            except OSError as exc:
                self.w.log(ut("failed", error=exc))
            if value is None:
                self.status(ut("current", version=self.version))
            elif not self.layout.frozen:
                self.status(ut("source"))
            else:
                self.status(ut("downloading", version=value.version, percent=0))
        elif kind == "progress":
            self.status(ut("downloading", version=value[0], percent=value[1]))
        elif kind == "download":
            self.download = value
            self.status(ut("available", version=self.release.version))
            if not self.manual:
                self.show_dialog()
        elif kind == "error":
            self.state["last_check"] = time.time()  # Background failures wait until the next daily check.
            try:
                write_state(self.state_path, self.state)
            except OSError:
                pass
            self.status(ut("failed", error=value))
            self.w.log(self.w.update_status.text())
        if kind in {"done", "cancelled", "error"}:
            self.cancel = None
            if kind == "cancelled":
                self.status(ut("cancelled"))
        self.refresh_dialog()

    def show_dialog(self):
        if self.dialog is None:
            self.dialog = QDialog(self.w)
            self.dialog.setWindowTitle(ut("title"))
            self.dialog.resize(620, 460)
            layout = QVBoxLayout(self.dialog)
            self.heading = QLabel()
            self.heading.setWordWrap(True)
            self.notes = QPlainTextEdit()
            self.notes.setReadOnly(True)
            self.dialog_status = QLabel()
            self.dialog_status.setWordWrap(True)
            layout.addWidget(self.heading)
            layout.addWidget(self.notes, 1)
            layout.addWidget(self.dialog_status)
            buttons = QHBoxLayout()
            self.open_button = QPushButton(ut("open"))
            self.open_button.clicked.connect(self.open_page)
            self.install_button = QPushButton(ut("install"))
            self.install_button.clicked.connect(self.install)
            later = QPushButton(ut("later"))
            later.clicked.connect(self.dialog.hide)
            for b in (self.open_button, self.install_button, later): buttons.addWidget(b)
            layout.addLayout(buttons)
        self.refresh_dialog()
        self.dialog.show()
        self.dialog.raise_()

    def refresh_dialog(self):
        if self.dialog is None:
            return
        r = self.release
        self.heading.setText(ut("new", version=r.version) if r else ut("title"))
        self.notes.setPlainText(r.notes if r else "")
        self.dialog_status.setText(self.w.update_status.text() + ("\n" + ut("verified") if self.download else ""))
        self.open_button.setEnabled(r is not None)
        self.install_button.setText(ut("repair") if self.repair else ut("install"))
        self.install_button.setEnabled(bool(r and self.download and self.layout.frozen and self.cancel is None))

    def open_page(self):
        if self.release:
            QDesktopServices.openUrl(QUrl(self.release.page))

    def prepare_handoff(self):
        from .program_update import running_instances
        if [pid for pid in running_instances(self.layout.app_dir) if pid != os.getpid()]:
            raise RuntimeError(ut("instances"))
        package, checksum = self.download
        if package.stat().st_size != self.release.size:
            raise ValueError(ut("package_changed"))
        folder = package.parent
        helper = folder / "WallpaperCompanionUpdater.exe"
        original_helper = self.layout.app_dir / helper.name
        if original_helper.is_file():
            shutil.copy2(original_helper, helper)
        elif not (self.repair and helper.is_file()):
            raise FileNotFoundError(ut("exe_missing"))
        plan = dict(target=str(self.layout.app_dir), archive=str(package), version=self.release.version,
                    sha256=checksum, size=self.release.size, portable=self.layout.portable,
                    parent_pid=os.getpid(), parent_started=psutil.Process().create_time(), language=language(), repair=self.repair)
        path = folder / "handoff.json"
        atomic_json(path, plan)
        self.state["pending_release"] = asdict(self.release)
        self.state["pending_result"] = str(folder / "result.json")
        write_state(self.state_path, self.state)
        return helper, path

    def install(self):
        if not self.layout.frozen or not self.download or self.cancel is not None:
            return
        if self.w.tts_busy or self.w.api_busy:
            QMessageBox.information(self.w, ut("title"), ut("busy"))
            return
        if QMessageBox.question(self.w, ut("title"), ut("confirm", version=self.release.version),
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if not self.w.autosave.flush():
            return
        try:
            helper, path = self.prepare_handoff()
            subprocess.Popen([str(helper), "--plan", str(path)], cwd=helper.parent, env=launch_environment(),
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as exc:
            self.status(ut("failed", error=exc))
            self.refresh_dialog()
            self.w.report_error(self.w.update_status.text())
            return
        self.w.cleanup()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def previous_result(self):
        if self.closed:
            return
        value = self.state.get("pending_result")
        if not value:
            return
        path = Path(value).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            return
        result = read_state(path)
        if not result:
            return
        message = (ut("success", version=result.get("version", self.version)) if result.get("success") else
                   ut("previous_failed", error=result.get("error", "")))
        if result.get("success"):
            self.state.pop("pending_result", None)
            self.state.pop("pending_release", None)
        elif self.layout.frozen and not self.layout.portable:
            try:
                release = Release(**self.state.get("pending_release", {}))
                plan = read_state(path.parent / "handoff.json")
                package = Path(plan["archive"]).resolve()
                if (package.parent != path.parent or not package.is_relative_to(self.root.resolve())
                        or package.name != release.name or not package.is_file()
                        or result.get("sha256") != plan["sha256"]
                        or result.get("version") != release.version
                        or Path(plan["target"]).resolve() != self.layout.app_dir.resolve()):
                    raise ValueError(ut("invalid_response"))
                self.release, self.download = release, (package, plan["sha256"])
                self.repair = True
            except (KeyError, TypeError, OSError, ValueError) as exc:
                self.w.log(ut("failed", error=exc))
        try:
            write_state(self.state_path, self.state)
        except OSError as exc:
            self.w.log(ut("failed", error=exc))
        self.status(message)
        self.w.autosave.show(message)
        if self.repair:
            self.show_dialog()

    def close(self):
        self.closed = True
        self.timer.stop()
        if self.cancel:
            self.cancel.set()
        if self.dialog:
            self.dialog.hide()
