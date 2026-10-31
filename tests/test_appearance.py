import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QColor, QImage

from companion.appearance import (PINK, background_path, extract_accent,
    normalize_appearance, prepare_background, save_appearance)
from companion.core import Store


class AppearanceTests(unittest.TestCase):
    def image(self, path, color="#286acb", size=(120, 80)):
        image = QImage(*size, QImage.Format.Format_ARGB32)
        image.fill(QColor(color))
        self.assertTrue(image.save(str(path)))
        return image

    def test_legacy_and_malformed_settings_are_safe(self):
        for value in [None, [], "bad", 12, {"background": "../../secret.jpg", "accent": "red;}QWidget{}", "auto_color": "false"}]:
            self.assertEqual(normalize_appearance(value), {"background": "", "accent": PINK, "auto_color": True})
        self.assertFalse(normalize_appearance({"auto_color": False})["auto_color"])

    def test_hue_is_retained_and_pastel_has_readable_contrast(self):
        import colorsys
        for color in ["#cc324e", "#22a854", "#286acb"]:
            image = QImage(20, 20, QImage.Format.Format_RGB32)
            image.fill(QColor(color))
            accent = QColor(extract_accent(image))
            original_hue = QColor(color).hslHueF()
            self.assertLess(abs(accent.hslHueF() - original_hue), .02)
            def luminance(c):
                channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in (c.redF(), c.greenF(), c.blueF())]
                return sum(a * b for a, b in zip(channels, (.2126, .7152, .0722)))
            self.assertGreater((luminance(accent) + .05) / (luminance(QColor("#19171e")) + .05), 7)
            self.assertGreater((luminance(accent) + .05) / (luminance(QColor("#281821")) + .05), 7)

    def test_grayscale_and_transparent_images_fall_back_to_pink(self):
        for color in ["#777777", "#000000", "#ffffff", "#002864cb"]:
            image = QImage(20, 20, QImage.Format.Format_ARGB32)
            image.fill(QColor(color))
            self.assertEqual(extract_accent(image), PINK)

    def test_import_is_managed_and_survives_removal_of_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "角色.png"
            self.image(source)
            original = source.read_bytes()
            prepared = prepare_background(source)
            store = Store(root / "data/config.json")
            settings = {"background": prepared["name"], "accent": prepared["accent"], "auto_color": True}
            save_appearance(store, settings, prepared)
            self.assertEqual(source.read_bytes(), original)
            source.unlink()
            reopened = Store(store.path)
            self.assertEqual(reopened.config["appearance"], settings)
            self.assertTrue(background_path(reopened).is_file())
            self.assertFalse(QImage(str(background_path(reopened))).isNull())

    def test_failed_config_save_restores_preferences_and_removes_new_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "角色.png"; self.image(source)
            store = Store(root / "data/config.json"); store.save()
            before = store.path.read_bytes()
            previous = store.config["appearance"].copy()
            prepared = prepare_background(source)
            settings = {**previous, "background": prepared["name"], "accent": prepared["accent"]}
            with patch.object(store, "save", side_effect=OSError("fixture save failure")):
                with self.assertRaises(OSError):
                    save_appearance(store, settings, prepared)
            self.assertEqual(store.config["appearance"], previous)
            self.assertEqual(store.path.read_bytes(), before)
            self.assertFalse(background_path(store, settings).exists())
            self.assertTrue(source.exists())

    def test_reset_does_not_delete_original_or_managed_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "角色.png"; self.image(source)
            prepared = prepare_background(source)
            store = Store(root / "data/config.json")
            settings = {"background": prepared["name"]}
            save_appearance(store, settings, prepared)
            managed = background_path(store)
            save_appearance(store, {})
            self.assertEqual(store.config["appearance"]["background"], "")
            self.assertTrue(source.exists())
            self.assertTrue(managed.exists())

    def test_downsample_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "wide.png"; self.image(source, size=(4096, 512))
            self.assertLessEqual(prepare_background(source)["image"].width(), 2048)
            corrupt = root / "corrupt.png"; corrupt.write_bytes(b"bad image")
            with self.assertRaises(ValueError):
                prepare_background(corrupt)

    def test_protected_output_is_rejected_before_configuration_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"; self.image(source)
            store = Store(root / "protected/config.json")
            store.config["we_dir"] = str(root / "protected")
            prepared = prepare_background(source)
            with self.assertRaises(ValueError):
                save_appearance(store, {"background": prepared["name"]}, prepared)
            self.assertEqual(store.config["appearance"]["background"], "")
            self.assertFalse((root / "protected/appearance").exists())


if __name__ == "__main__":
    unittest.main()
