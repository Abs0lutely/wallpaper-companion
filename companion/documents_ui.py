"""Read bundled Markdown in-app instead of relying on Windows file associations."""
from .i18n import tr, language
from pathlib import Path
import re

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QColor, QImage, QPalette, QTextDocument, QTextCursor, QTextBlockFormat, QTextOption
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTextBrowser, QVBoxLayout


LOCALIZED_DOCUMENTS = {
    "USER_GUIDE.md": ("USER_GUIDE.md", "USER_GUIDE.en.md"),
    "USER_GUIDE.en.md": ("USER_GUIDE.md", "USER_GUIDE.en.md"),
    "USAGE.md": ("USAGE.md", "USAGE.en.md"),
    "USAGE.en.md": ("USAGE.md", "USAGE.en.md"),
    # GitHub's promotional HTML/images are not suitable for the native reader.
    "README.md": ("USAGE.md", "USAGE.en.md"),
    "README.en.md": ("USAGE.md", "USAGE.en.md"),
}


def document_path(root, path):
    root = Path(root).resolve()
    path = Path(path).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".md":
        raise ValueError(tr('ui.278616ac1680', '只能在手册窗口中打开程序目录内的 Markdown 文档'))
    if path.parent == root and path.name in LOCALIZED_DOCUMENTS:
        path = root / LOCALIZED_DOCUMENTS[path.name][language() == "en-US"]
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError(tr('ui.278616ac1680', '只能在手册窗口中打开程序目录内的 Markdown 文档'))
    return path


def reading_markdown(content):
    """Reflow wide reference tables into labelled paragraphs for narrow windows."""
    lines = content.splitlines()
    output = []
    i = 0
    def cells(line):
        return [c.strip() for c in line.strip().strip("|").split("|")]
    while i < len(lines):
        if (i + 1 < len(lines) and lines[i].lstrip().startswith("|")
                and re.fullmatch(r"\s*\|?[\s:|\-]+\|?\s*", lines[i+1])
                and "-" in lines[i+1]):
            headings = cells(lines[i])
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                row = cells(lines[i])
                if row:
                    output.extend(["**" + row[0] + "**", ""])
                    for index, value in enumerate(row[1:], 1):
                        prefix = "**" + headings[index] + ":** " if len(headings) > 2 and index < len(headings) else ""
                        output.extend([prefix + value, ""])
                i += 1
            continue
        output.append(lines[i])
        i += 1
    return "\n".join(output)


class ReadingBrowser(QTextBrowser):
    def loadResource(self, kind, url):
        # Reading help must not load online badges or huge promotional pictures.
        if kind == QTextDocument.ResourceType.ImageResource:
            return QImage()
        return super().loadResource(kind, url)


class DocumentViewer(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = Path(root).resolve()
        self.current_path = None
        self.setObjectName("documentationViewer")
        self.resize(1000, 760)
        self.setMinimumSize(640, 440)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.browser = ReadingBrowser()
        self.browser.setObjectName("documentationText")
        self.setStyleSheet("""
            QDialog#documentationViewer {background:#f5f2f6; background-image:none;}
            QTextBrowser#documentationText, QTextBrowser#documentationText QWidget {
                background:#fffdf9; background-image:none; color:#302c35;
                selection-background-color:#e4d5f0; selection-color:#231d2a;
                border:0; border-radius:0; padding:0;
                font-family:'Microsoft YaHei UI'; font-size:15px;
            }
            QDialogButtonBox QPushButton {background:#eee7f1; color:#302c35; border:1px solid #b6a9bd;}
            QDialogButtonBox QPushButton:hover {background:#e3d6eb;}
        """)
        palette = self.browser.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#fffdf9"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#302c35"))
        self.browser.setPalette(palette)
        self.browser.viewport().setPalette(palette)
        self.browser.viewport().setAutoFillBackground(True)
        self.browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.browser.document().setDocumentMargin(24)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.document().setDefaultStyleSheet(
            "body {color:#302c35; background-color:#fffdf9;} "
            "a {color:#70409a;} code {font-family:Consolas; color:#59416b;}"
        )
        self.browser.anchorClicked.connect(self.follow_link)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
        layout.addWidget(buttons)

    def load_document(self, path):
        path = document_path(self.root, path)
        # Read before replacing the visible document so failed navigation is harmless.
        content = path.read_text(encoding="utf-8-sig")
        self.current_path = path
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(path.parent) + "/"))
        self.browser.document().setMarkdown(reading_markdown(content), QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML)
        cursor = QTextCursor(self.browser.document())
        cursor.select(QTextCursor.SelectionType.Document)
        paragraph = QTextBlockFormat()
        paragraph.setLineHeight(145, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        paragraph.setTopMargin(5)
        paragraph.setBottomMargin(10)
        cursor.mergeBlockFormat(paragraph)
        self.browser.setTextCursor(QTextCursor(self.browser.document()))
        self.browser.verticalScrollBar().setValue(0)
        if path.name in {"USER_GUIDE.md", "USER_GUIDE.en.md"}:
            title = tr('ui.396c685466aa', '使用手册')
        elif path.name in {"USAGE.md", "USAGE.en.md"}:
            title = tr("documents.overview", "使用说明")
        else:
            title = path.stem
        self.setWindowTitle(tr('ui.aa7c274c3e56', '壁纸声伴 · ') + title)

    def follow_link(self, url):
        try:
            if url.scheme() in {"http", "https"}:
                if not QDesktopServices.openUrl(url):
                    raise ValueError(tr('ui.6f2203b69579', '系统未能打开网页，请检查默认浏览器'))
                return
            if url.scheme() not in {"", "file"}:
                raise ValueError(tr('ui.7363896a302b', '不支持此类文档链接'))
            path = (Path(url.toLocalFile()) if url.isLocalFile() else
                    self.current_path.parent / url.path() if url.path() else self.current_path)
            if path.resolve() != self.current_path:
                self.load_document(path)
            if url.fragment():
                self.browser.scrollToAnchor(url.fragment())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr('ui.8c0c99b071d5', '无法打开说明'), str(exc))
