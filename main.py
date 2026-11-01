import os
import sys

def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        try:
            from companion.diagnostics import run
            return run(sys.argv[2])
        except Exception:
            import json
            import traceback
            from pathlib import Path
            target = Path(sys.argv[2])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({"passed": False, "error": traceback.format_exc()}), encoding="utf-8")
            return 1
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox
    from companion.core import DATA, Store, writable_path
    from companion.i18n import set_language, install_qt_translation
    app = QApplication(sys.argv)
    try:
        store = Store()
    except Exception as exc:
        QMessageBox.critical(None, "启动失败 / Startup failed", str(exc))
        return 1
    set_language(store.config.get("ui_language"))
    from companion.ui import STYLE, Window, app_icon
    install_qt_translation(app)
    app.setWindowIcon(app_icon())
    app.setApplicationName("Wallpaper Companion")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    writable_path(DATA).mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(DATA / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(50):
        if "--tray" not in sys.argv:
            QMessageBox.information(None, "壁纸声伴已运行", "程序已在运行，请双击系统托盘中的粉发耳机少女图标打开配置。")
        return 0
    try:
        window = Window(store)
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
