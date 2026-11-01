"""Validated appearance preferences and managed, local background images."""
from __future__ import annotations
from .i18n import tr

import colorsys
import hashlib
import re
import uuid
from pathlib import Path

PINK = "#edb2c4"
DEFAULTS = {"background": "", "accent": PINK, "auto_color": True}


def normalize_appearance(value):
    if not isinstance(value, dict):
        return DEFAULTS.copy()
    background = value.get("background", "")
    if not isinstance(background, str) or not re.fullmatch(r"(?:[0-9a-f]{64}\.jpg)?", background):
        background = ""
    accent = value.get("accent", PINK)
    if not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = PINK
    # Old or manually edited preferences cannot introduce extra paths or QSS.
    return {"background": background, "accent": accent.lower(),
            "auto_color": value.get("auto_color") if type(value.get("auto_color")) is bool else True}


def background_path(store, settings=None):
    settings = normalize_appearance(settings if settings is not None else store.config.get("appearance"))
    return store.path.parent / "appearance" / settings["background"] if settings["background"] else None


def extract_accent(image):
    """Dominant chromatic hue, softened to a readable pastel on the dark shell."""
    from PySide6.QtCore import Qt
    sample = image.scaled(72, 48, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
    buckets = {}
    for y in range(sample.height()):
        for x in range(sample.width()):
            color = sample.pixelColor(x, y)
            if color.alpha() < 128:
                continue
            hue, light, saturation = colorsys.rgb_to_hls(color.redF(), color.greenF(), color.blueF())
            if saturation < .17 or not .12 < light < .9:
                continue
            weight = saturation * (1 - abs(light - .55))
            bucket = buckets.setdefault(int(hue * 24), [0., 0.])
            bucket[0] += weight
            bucket[1] += hue * weight
    if not buckets:
        return PINK
    score, weighted_hue = max(buckets.values(), key=lambda item: item[0])
    channels = colorsys.hls_to_rgb(weighted_hue / score, .77, .48)
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in channels)


def prepare_background(source):
    """Decode and downsample in a worker. Do not touch Qt widgets or user config."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
    from PySide6.QtGui import QColor, QImage, QImageReader, QPainter
    path = Path(source)
    if not path.is_file() or path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError(tr('ui.1530bc656a3d', '请选择 30 MB 以内的本地图片。'))
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 100_000_000:
        raise ValueError(tr('ui.0df54c294a23', '图片尺寸无效或过大，请使用不超过一亿像素的图片。'))
    if max(size.width(), size.height()) > 2048:
        reader.setScaledSize(size.scaled(QSize(2048, 2048), Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ValueError(tr('ui.e760baf5ac0d', '无法读取这张图片，请选择 PNG、JPEG、WebP 或 BMP。'))
    # Flatten transparent artwork onto the product background before JPEG encoding.
    flattened = QImage(image.size(), QImage.Format.Format_RGB32)
    flattened.fill(QColor("#19171e"))
    painter = QPainter(flattened)
    painter.drawImage(0, 0, image)
    painter.end()
    image = flattened
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "JPG", 88):
        raise ValueError(tr('ui.14abb54bd78d', '保存背景副本失败。'))
    payload = bytes(data)
    return {"image": image, "data": payload, "accent": extract_accent(image),
            "name": hashlib.sha256(payload).hexdigest() + ".jpg"}


def save_appearance(store, settings, prepared=None):
    """Commit preferences only after a managed image is ready; roll back on failure."""
    from .core import writable_path
    settings = normalize_appearance(settings)
    target = background_path(store, settings)
    created = False
    if prepared is not None:
        if settings["background"] != prepared["name"]:
            raise ValueError(tr('ui.ba30ec11cfb8', '背景名称不匹配。'))
        target = writable_path(target, store.protected())
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temp = writable_path(target.with_suffix(f".{uuid.uuid4().hex}.tmp"), store.protected())
            try:
                temp.write_bytes(prepared["data"])
                temp.replace(target)
                created = True
            finally:
                temp.unlink(missing_ok=True)
    existed = "appearance" in store.config
    old = store.config.get("appearance")
    store.config["appearance"] = settings
    try:
        store.save()
    except Exception:
        if existed:
            store.config["appearance"] = old
        else:
            store.config.pop("appearance", None)
        if created:
            target.unlink(missing_ok=True)
        raise
    return settings
