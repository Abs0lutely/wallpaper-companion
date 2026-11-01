"""Startup-selected UI translations. User content is never translated implicitly."""
from __future__ import annotations

_LANGUAGE = "zh-CN"
LANGUAGES = ("zh-CN", "en-US")


def normalize_language(value):
    return value if isinstance(value, str) and value in LANGUAGES else "zh-CN"


def set_language(value):
    global _LANGUAGE
    _LANGUAGE = normalize_language(value)


def language():
    return _LANGUAGE


def tr(key, fallback, **values):
    text = fallback
    if _LANGUAGE == "en-US":
        from .translations_en import EN
        text = EN.get(key, fallback)
    return text.format(**values) if values else text


def source_text(text):
    """Recover builtin captions for legacy semantic classification, never for data."""
    if _LANGUAGE == "en-US":
        from .translations_en import SOURCES, EN
        for key, value in EN.items():
            if value == text:
                return SOURCES.get(key, text)
    return text


def install_qt_translation(app):
    from PySide6.QtCore import QLibraryInfo, QTranslator
    translator = QTranslator(app)
    if _LANGUAGE == "zh-CN" and translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    # Retain the translator for the lifetime of QApplication.
    app._companion_translator = translator
