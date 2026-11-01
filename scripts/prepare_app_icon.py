r"""Convert the approved PNG artwork into a multi-resolution Windows ICO.

Only resizes/encodes the image; never redraws or changes the artwork.
Run from the project root: .\.conda\python.exe scripts/prepare_app_icon.py
"""
import struct
from pathlib import Path
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def prepare(source=None, destination=None):
    source = Path(source) if source else ROOT / "readme-assets/app-icon.png"
    destination = Path(destination) if destination else ROOT / "readme-assets/app-icon.ico"
    image = QImage(str(source))
    if image.isNull() or image.width() != image.height() or image.width() < 256:
        raise ValueError("Icon master must be a valid square PNG of at least 256 pixels.")
    frames = []
    for size in SIZES:
        frame = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not frame.save(buffer, "PNG"):
            raise ValueError("Cannot encode icon size: " + str(size))
        frames.append(bytes(data))
    offset = 6 + 16 * len(frames)
    directory = []
    for size, data in zip(SIZES, frames):
        directory.append(struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
                                     0, 0, 1, 32, len(data), offset))
        offset += len(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(struct.pack("<HHH", 0, 1, len(frames)) + b"".join(directory) + b"".join(frames))
    return destination


if __name__ == "__main__":
    print(prepare())
