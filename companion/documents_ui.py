"""Read bundled Markdown in-app instead of relying on Windows file associations."""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTextBrowser, QVBoxLayout


class DocumentViewer(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = Path(root).resolve()
        self.current_path = None
        self.setObjectName("documentationViewer")
        self.resize(1000, 760)
        self.setMinimumSize(640, 440)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.document().setDefaultStyleSheet(
            "body {line-height:1.5} table {border-collapse:collapse} "
            "td, th {border:1px solid #475569; padding:6px} "
            "a {color:#67e8c8} code {font-family:Consolas}"
        )
        self.browser.anchorClicked.connect(self.follow_link)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
        layout.addWidget(buttons)

    def load_document(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() != ".md":
            raise ValueError("只能在手册窗口中打开程序目录内的 Markdown 文档")
        # Read before replacing the visible document so failed navigation is harmless.
        content = path.read_text(encoding="utf-8-sig")
        self.current_path = path
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(path.parent) + "/"))
        self.browser.setMarkdown(content)
        self.browser.verticalScrollBar().setValue(0)
        self.setWindowTitle("壁纸声伴 · " + ("使用手册" if path.name == "USER_GUIDE.md" else path.stem))

    def follow_link(self, url):
        try:
            if url.scheme() in {"http", "https"}:
                if not QDesktopServices.openUrl(url):
                    raise ValueError("系统未能打开网页，请检查默认浏览器")
                return
            if url.scheme() not in {"", "file"}:
                raise ValueError("不支持此类文档链接")
            path = (Path(url.toLocalFile()) if url.isLocalFile() else
                    self.current_path.parent / url.path() if url.path() else self.current_path)
            if path.resolve() != self.current_path:
                self.load_document(path)
            if url.fragment():
                self.browser.scrollToAnchor(url.fragment())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "无法打开说明", str(exc))
