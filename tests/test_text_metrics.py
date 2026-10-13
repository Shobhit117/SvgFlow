import unittest

from svgflow.text_metrics import text_width


class TextWidthTests(unittest.TestCase):
    def test_width_uses_glyph_metrics(self):
        self.assertGreater(text_width("WWWW", 16), text_width("iiii", 16))

    def test_width_scales_with_font_size(self):
        self.assertAlmostEqual(text_width("legend", 20), 2 * text_width("legend", 10))

    def test_negative_size_is_rejected(self):
        with self.assertRaises(ValueError):
            text_width("legend", -1)


if __name__ == "__main__":
    unittest.main()
