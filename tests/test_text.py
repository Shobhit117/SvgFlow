import glob
import os
import re
import tempfile
import unittest

from svgflow import Canvas, register_font, text_width, wrap_text


def _system_ttf():
    for pattern in (r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/**/DejaVuSans.ttf", "/Library/Fonts/*.ttf"):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return hits[0]
    return None


class AddTextTests(unittest.TestCase):
    def test_single_line_has_no_tspan_and_is_escaped(self):
        c = Canvas(100, 100)
        c.addText("A < B & C", 10, 10)
        self.assertNotIn("<tspan", c.contents[-1])
        self.assertIn("A &lt; B &amp; C", c.contents[-1])

    def test_newlines_and_lists_produce_same_output(self):
        a, b = Canvas(100, 100), Canvas(100, 100)
        a.addText("one\ntwo\nthree", 0, 0)
        b.addText(["one", "two", "three"], 0, 0)
        self.assertEqual(a.contents, b.contents)
        self.assertEqual(a.contents[-1].count("<tspan"), 3)

    def test_middle_baseline_centres_block(self):
        c = Canvas(100, 100)
        c.addText("a\nb\nc", 0, 0, line_height=1.2)
        self.assertIn('dy="-1.2000em"', c.contents[-1])

    def test_valign_top_keeps_first_line_at_y(self):
        c = Canvas(100, 100)
        c.addText("a\nb", 0, 0, valign="top")
        self.assertIn('dy="0.0000em"', c.contents[-1])

    def test_text_top_baseline_emits_auto_for_cross_browser_consistency(self):
        c = Canvas(100, 100)
        c.addText("a\nb", 0, 0, baseline="text-top")
        self.assertIn('dominant-baseline="auto"', c.contents[-1])
        self.assertIn('dy="-1.2000em"', c.contents[-1])

    def test_wrapping_respects_max_width(self):
        text = "the quick brown fox jumps over the lazy dog"
        lines = wrap_text(text, 16, 100)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(text_width(line, 16), 100)
        c = Canvas(100, 100)
        w, h = c.addText(text, 0, 0, max_width=100)
        self.assertLessEqual(w, 100)
        self.assertAlmostEqual(h, len(lines) * 1.2 * 16)

    def test_builtin_fonts_and_bold_measurement(self):
        self.assertGreater(text_width("Hello", 16, bold=True), text_width("Hello", 16))
        self.assertNotAlmostEqual(text_width("iiii", 16, "mono"), text_width("iiii", 16, "sans"))
        c = Canvas(100, 100)
        c.addText("x", 0, 0, font="serif")
        self.assertIn("Times New Roman", c.contents[-1])

    def test_unknown_font_raises(self):
        with self.assertRaises(KeyError):
            Canvas(10, 10).addText("x", 0, 0, font="does-not-exist")

    def test_multiline_wrapper_still_works(self):
        c = Canvas(100, 100)
        c.addMultiLineText(["a", "b"], 0, 0)
        self.assertEqual(c.contents[-1].count("<tspan"), 2)

    @unittest.skipIf(_system_ttf() is None, "no system TTF available")
    def test_registered_font_is_measured_and_embedded(self):
        path = _system_ttf()
        register_font("TestFont", path)
        self.assertGreater(text_width("Hello", 16, "TestFont"), 0)
        c = Canvas(100, 100)
        c.addText("Hello", 10, 10, font="TestFont")
        self.assertIn("font-family=\"'TestFont'", c.contents[-1])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "f.svg")
            c.save(out)
            with open(out, encoding="utf-8") as f:
                svg = f.read()
        self.assertRegex(svg, r"@font-face \{ font-family: 'TestFont'.*base64,")


if __name__ == "__main__":
    unittest.main()
