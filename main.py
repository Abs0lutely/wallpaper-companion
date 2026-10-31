import os
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from companion.core import DATA, Store, writable_path
from companion.ui import STYLE, Window


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wallpaper Companion")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    writable_path(DATA).mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(DATA / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(50):
        if "--tray" not in sys.argv:
            QMessageBox.information(None, "壁纸声伴已运行", "程序已在运行，请双击系统托盘中的绿色声波图标打开配置。")
        return 0
    try:
        window = Window(Store())
    except Exception as exc:
        QMessageBox.critical(None, "启动失败", str(exc))
        return 1
    app.aboutToQuit.connect(window.cleanup)
    if "--tray" not in sys.argv:
        window.show()
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    sys.exit(main())
