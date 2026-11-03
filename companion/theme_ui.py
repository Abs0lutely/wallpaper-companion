"""The companion's dark rose design tokens, shared by native widgets and dialogs."""
from .appearance import PINK, normalize_appearance


def stylesheet(accent=PINK):
    accent = normalize_appearance({"accent": accent})["accent"]
    rgb = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5))
    soft = "#" + "".join(f"{round(v * .14 + base):02x}" for v, base in zip(rgb, (25, 23, 30)))
    return """
QWidget { background:transparent; color:#f3edf0; font-family:'Microsoft YaHei UI'; font-size:13px; }
QMainWindow, QDialog, QWidget#shell { background:#19171e; }
QWidget#workspace, QWidget#content, QWidget#page, QScrollArea>QWidget>QWidget { background:transparent; }
QLabel { background:transparent; }
QLabel#brand { font-size:19px; font-weight:600; letter-spacing:2px; }
QLabel#pageTitle { font-size:22px; font-weight:600; }
QLabel#sectionTitle { font-size:15px; font-weight:600; padding-bottom:8px; }
QLabel#subtle { color:#b7adbd; }
QLabel#current { color:#fff3f7; font-size:23px; font-weight:600; padding:0; }
QLabel#heroCaption { color:#efdae4; font-size:12px; }
QLabel#status { color:ACCENT; padding:2px 0; }
QFrame#sidebar { background:#19171e; border-right:1px solid #39333e; }
QFrame#card { background:#232129; border:1px solid #39333e; border-radius:16px; }
QFrame#player { background:#232129; border-top:1px solid #39333e; }
QPushButton { background:#2b2731; border:1px solid #423a48; border-radius:9px; padding:8px 12px; }
QPushButton:hover { background:SOFT; border-color:ACCENT; }
QPushButton:pressed { background:#43323d; }
QPushButton:disabled { color:#817787; border-color:#39333e; background:#242129; }
QPushButton#primary { background:ACCENT; border-color:ACCENT; color:#281821; font-weight:600; }
QPushButton#primary:hover { color:#17121b; }
QPushButton#nav { text-align:left; background:transparent; border:0; padding:10px 14px; color:#b7adbd; }
QPushButton#nav:checked { background:SOFT; color:ACCENT; }
QPushButton#nav:hover { background:#29242e; }
QPushButton#homeTab { background:transparent; border:0; border-bottom:2px solid transparent; border-radius:0; padding:9px 12px; color:#b7adbd; }
QPushButton#homeTab:checked { color:ACCENT; border-bottom:2px solid ACCENT; }
QLineEdit, QPlainTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {
 background:#1d1a23; border:1px solid #443b4b; border-radius:7px; padding:7px; selection-background-color:SOFT; selection-color:#f3edf0; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color:ACCENT; }
QComboBox::drop-down { width:22px; border:0; }
QComboBox QAbstractItemView { background:#232129; selection-background-color:SOFT; color:#f3edf0; }
QListWidget, QTableView { background:#201d26; border:1px solid #39333e; border-radius:9px; alternate-background-color:#26212c; gridline-color:#39333e; }
QListWidget::item { padding:10px 7px; border-radius:6px; }
QListWidget::item:selected, QTableView::item:selected { background:SOFT; color:ACCENT; }
QHeaderView::section { background:#2b2531; border:0; border-bottom:1px solid #39333e; padding:10px 7px; color:#c5b9ca; }
QTabWidget::pane { border:0; background:transparent; }
QTabBar::tab { background:transparent; color:#b7adbd; padding:10px 16px; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:ACCENT; border-bottom:2px solid ACCENT; }
QCheckBox { spacing:8px; padding:5px 0; background:transparent; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #817187; border-radius:5px; background:#1d1a23; }
QCheckBox::indicator:checked { background:ACCENT; border:2px solid ACCENT; image:url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); }
QSlider { background:transparent; }
QSlider::groove:horizontal { height:4px; background:#514653; border:0; border-radius:2px; }
QSlider::sub-page:horizontal { background:ACCENT; border-radius:2px; }
QSlider::handle:horizontal { width:14px; margin:-5px 0; border-radius:7px; background:ACCENT; }
QMenu { background:#28222e; border:1px solid #54465c; padding:5px; }
QMenu::item { padding:9px 22px; border-radius:6px; }
QMenu::item:selected { background:SOFT; color:ACCENT; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:#211d27; width:9px; margin:0; }
QScrollBar::handle:vertical { background:#55495d; min-height:28px; border-radius:4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QToolTip { background:#322a39; color:#f3edf0; border:1px solid #67566f; padding:6px; }
QProgressBar { border:1px solid #514653; border-radius:5px; background:#211d27; color:#f3edf0; text-align:center; min-height:16px; }
QProgressBar::chunk { background:SOFT; border-radius:4px; }
QStatusBar { background:#211d27; color:#c5b8c9; border-top:1px solid #39333e; }
QSplitter::handle { background:#39333e; }
""".replace("ACCENT", accent).replace("SOFT", soft)
