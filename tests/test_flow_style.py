import glob
import os
import re
import shutil
import tempfile
import unittest

import numpy as np

from svgflow import Canvas, Flow, FlowStyle
from svgflow.inkscape_fonts import build_fontconfig, inkscape_font_env
from svgflow.text_metrics import get_font, register_font


def _path_numbers(svg: str) -> list[float]:
    d = re.search(r'd="([^"]+)"', svg).group(1)
    return [float(v) for v in re.findall(r'-?\d+\.?\d*', d)]


class FlowGeometryTests(unittest.TestCase):
    def test_ellipse_boundary_is_on_the_ray_and_the_outline(self):
        f = Flow(400, 400)
        f.addNode("e", 200, 200, ("ellipse", 90, 40))
        for theta in (10, 33, 60, 135, 250, 300):
            x, y = f._getIntersectionWithContainer("e", theta)
            self.assertAlmostEqual(((x - 200) / 90) ** 2 + ((y - 200) / 40) ** 2, 1, places=9)
            self.assertAlmostEqual(np.degrees(np.arctan2(y - 200, x - 200)) % 360, theta % 360, places=6)

    def test_rounded_rectangle_corner(self):
        f = Flow(400, 400)
        f.addNode("r", 200, 200, ("rectangle", 90, 140, 30))
        x, y = f._getIntersectionWithContainer("r", -45)
        # on the top-right corner arc (centre (240, 185), radius 30) ...
        self.assertAlmostEqual(np.hypot(x - 240, y - 185), 30, places=9)
        # ... and on the ray from the node centre
        self.assertAlmostEqual(np.degrees(np.arctan2(y - 200, x - 200)), -45, places=6)
        # straight sides are unaffected
        self.assertEqual(tuple(map(float, f._getIntersectionWithContainer("r", 0))), (270.0, 200.0))

    def test_curved_edge_between_vertically_aligned_nodes(self):
        f = Flow(400, 400)
        f.addNode("t", 200, 60, ("rectangle", 40, 90))
        f.addNode("b", 200, 260, ("rectangle", 40, 90))
        f.addEdge("t", "b", curvature=60)
        nums = _path_numbers(f.contents[-1])
        # control point is (260, 160); the curve leaves t's bottom side heading for it
        self.assertAlmostEqual(nums[0], 212, places=3)
        self.assertAlmostEqual(nums[1], 80, places=3)
        self.assertEqual(nums[2:4], [260, 160])
        self.assertAlmostEqual(nums[4], 212, places=3)
        self.assertAlmostEqual(nums[5], 240, places=3)

    def test_self_loops_bulge_outward(self):
        f = Flow(400, 400)
        f.addNode("c", 200, 200, ("circle", 40))
        for theta1, theta2 in ((60, 120), (-120, -60), (-20, 20), (160, 200)):
            f.addSelfEdge("c", theta1, theta2)
            nums = _path_numbers(f.contents[-1])
            pts = np.array(nums).reshape(-1, 2)
            apex = 0.125 * pts[0] + 0.375 * pts[1] + 0.375 * pts[2] + 0.125 * pts[3]
            self.assertGreater(np.hypot(*(apex - 200)), 40 + 30, (theta1, theta2))


class EdgeLabelSideTests(unittest.TestCase):
    """Labels must grow away from their edge, including for vertical edges."""

    def _label(self, c):
        el = next(e for e in reversed(c.contents) if e.startswith("<text"))
        x, y = map(float, re.search(r'translate\(([-0-9.]+) ([-0-9.]+)\)', el).groups())
        rot = float(re.search(r'rotate\(([-0-9.]+)\)', el).group(1))
        baseline = re.search(r'dominant-baseline="([^"]+)"', el).group(1)
        return x, y, rot, baseline

    def _grow_direction(self, rot, baseline):
        # Unit vector the multi-line block grows towards (text "up" for text-top, "down" for hanging).
        up = np.array([np.sin(np.deg2rad(rot)), -np.cos(np.deg2rad(rot))])
        return up if baseline == "text-top" else -up

    def test_straight_edges_all_directions(self):
        for (x2, y2) in ((100, 0), (-100, 0), (0, 100), (0, -100), (70, 70), (-70, 70)):
            c = Canvas(300, 300)
            c.addLine(0, 0, x2, y2, label="a\nb")
            x, y, rot, baseline = self._label(c)
            offset = np.array([x - x2 / 2, y - y2 / 2])
            grow = self._grow_direction(rot, baseline)
            self.assertGreater(float(offset @ grow), 0, (x2, y2))  # placed on the side it grows toward

    def test_vertical_curved_edges(self):
        for curvature in (40, -40):
            c = Canvas(300, 300)
            c.addCurvedLine(0, 0, 0, 200, curvature, label="a\nb")
            x, y, rot, baseline = self._label(c)
            self.assertEqual(np.sign(x), np.sign(curvature))  # outside the bulge
            self.assertEqual(np.sign(self._grow_direction(rot, baseline)[0]), np.sign(curvature))


class FlowStyleTests(unittest.TestCase):
    def test_style_defaults_apply_everywhere(self):
        style = FlowStyle(node_color="aliceblue", node_border="navy", edge_color="gray", edge_thickness=3, arrow_style="stealth", text_size=12)
        f = Flow(300, 300, style=style)
        f.addNode("a", 50, 50, label="A")
        f.addNode("b", 250, 50, ("rectangle", 30, 60))
        self.assertIn('fill="aliceblue"', f.contents[0])
        self.assertIn('stroke="navy"', f.contents[0])
        self.assertIn('font-size="12"', f.contents[1])
        f.addEdge("a", "b", directed=True)
        self.assertIn('stroke="gray"', f.contents[-2])
        self.assertIn('stroke-width="3"', f.contents[-2])
        self.assertIn("#arrow_stealth", f.contents[-1])
        f.addElbowEdge("a", "b", from_port="S", to_port="S", color="red")
        self.assertIn('stroke="red"', f.contents[-2])  # explicit arguments still win

    def test_copy(self):
        s = FlowStyle(edge_color="gray").copy(text_size=10)
        self.assertEqual((s.edge_color, s.text_size), ("gray", 10))


def _non_system_ttf():
    try:
        import matplotlib
    except ImportError:
        return None
    hits = glob.glob(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSerif-Bold.ttf"))
    return hits[0] if hits else None


class InkscapeFontTests(unittest.TestCase):
    def test_config_contains_folder_rules_and_base_include(self):
        xml = build_fontconfig(r"C:\tmp\fonts", r"C:\tmp\cache", [("My Font", r"C:\tmp\fonts\svgflow-x-000-face.ttf")], r"C:\base\fonts.conf")
        self.assertIn("<dir>C:/tmp/fonts</dir>", xml)
        self.assertIn('<string>svgflow-x-000-face.ttf</string>', xml)
        self.assertIn('<string>My Font</string>', xml)
        self.assertIn('<include ignore_missing="yes">C:/base/fonts.conf</include>', xml)

    def test_no_file_fonts_means_no_env(self):
        with inkscape_font_env([get_font("serif")]) as env:
            self.assertIsNone(env)

    @unittest.skipIf(_non_system_ttf() is None, "no test font available")
    def test_env_exposes_copied_font(self):
        spec = register_font("InkTestFont", _non_system_ttf())
        with inkscape_font_env([spec]) as env:
            if env is None:
                self.skipTest("no base fontconfig found")
            conf = env["FONTCONFIG_FILE"]
            self.assertTrue(os.path.isfile(conf))
            font_dir = os.path.join(os.path.dirname(conf), "fonts")
            self.assertEqual(len(os.listdir(font_dir)), 1)
        self.assertFalse(os.path.exists(conf))  # cleaned up

    @unittest.skipIf(_non_system_ttf() is None or shutil.which("inkscape") is None, "needs inkscape and a test font")
    def test_inkscape_pdf_uses_registered_font(self):
        import pymupdf
        c = Canvas(60, 300)
        c.registerFont("InkTestFont2", _non_system_ttf())
        c.addText("Hello", 150, 30, font="InkTestFont2")
        with tempfile.TemporaryDirectory() as d:
            pdf = os.path.join(d, "t.pdf")
            c.export(pdf, "pdf")
            fonts = [f[3] for f in pymupdf.open(pdf)[0].get_fonts()]
        self.assertTrue(any("DejaVuSerif-Bold" in name for name in fonts), fonts)


if __name__ == "__main__":
    unittest.main()

