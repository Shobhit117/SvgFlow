import re
import unittest

import numpy as np

from svgflow import Canvas, Flow


def _line_end(svg: str) -> tuple[float, float]:
    m = re.search(r'x2="([-0-9.]+)" y2="([-0-9.]+)"', svg)
    return float(m.group(1)), float(m.group(2))


def _use_transform(svg: str) -> tuple[float, float, float, float]:
    m = re.search(r'translate\(([-0-9.]+) ([-0-9.]+)\) rotate\(([-0-9.]+)\) scale\(([-0-9.]+)', svg)
    return tuple(float(v) for v in m.groups())


class ArrowTests(unittest.TestCase):
    def test_directed_variants(self):
        for directed, n_heads in ((False, 0), (True, 1), ("end", 1), ("start", 1), ("both", 2)):
            c = Canvas(100, 100)
            c.addLine(0, 0, 50, 0, directed=directed)
            self.assertEqual(sum("<use" in e for e in c.contents), n_heads, directed)
        with self.assertRaises(ValueError):
            Canvas(10, 10).addLine(0, 0, 1, 1, directed="sideways")

    def test_stroke_is_trimmed_so_it_ends_inside_the_head(self):
        c = Canvas(100, 100)
        c.addLine(0, 0, 100, 0, thickness=2, directed=True, arrow_style="triangle")
        x2, _ = _line_end(c.contents[0])
        self.assertAlmostEqual(x2, 95, places=3)  # half of the 10px head
        x, y, theta, _ = _use_transform(c.contents[1])
        self.assertEqual((x, y, theta), (100, 0, 0))  # filled tip lands exactly on the end point

    def test_head_scales_with_thickness(self):
        c = Canvas(100, 100)
        c.addLine(0, 0, 100, 0, thickness=6, directed=True)
        self.assertAlmostEqual(_use_transform(c.contents[1])[3], 3)
        c.addLine(0, 0, 100, 0, thickness=1, directed=True, arrow_size=2)
        self.assertAlmostEqual(_use_transform(c.contents[-1])[3], 2)

    def test_start_arrow_points_backwards(self):
        c = Canvas(100, 100)
        c.addLine(0, 0, 100, 0, directed="start")
        x, y, theta, _ = _use_transform(c.contents[1])
        self.assertAlmostEqual(theta, 180)

    def test_canvas_default_style_and_defs_are_reused(self):
        c = Canvas(100, 100)
        c.arrow_style = "stealth"
        c.addLine(0, 0, 10, 0, directed=True)
        c.addLine(0, 10, 10, 10, directed=True)
        self.assertEqual(sum('id="arrow_stealth"' in d for d in c.defs), 1)
        with self.assertRaises(ValueError):
            c.addLine(0, 0, 1, 1, directed=True, arrow_style="banana")

    def test_translucent_arrows_are_grouped(self):
        c = Canvas(100, 100)
        c.addLine(0, 0, 50, 0, directed=True, opacity=0.5)
        self.assertEqual(len(c.contents), 1)
        self.assertTrue(c.contents[0].startswith('<g opacity="0.5">'))

    def test_curved_paths_and_arcs_use_end_tangent(self):
        c = Canvas(100, 100)
        c.addQuadraticPath([(0, 0), (100, 0)], [(50, 50)], directed=True)
        self.assertAlmostEqual(_use_transform(c.contents[-1])[2], np.degrees(np.arctan2(-50, 50)), places=3)
        # cubic whose last control point coincides with the end point
        c.addCubicPath([(0, 0), (100, 0)], [(0, 100)], [(100, 0)], directed=True)
        self.assertAlmostEqual(_use_transform(c.contents[-1])[2], np.degrees(np.arctan2(-100, 100)), places=3)
        c.addCircularArc(50, 50, 40, 0, 90, directed=True)
        x, y, theta, _ = _use_transform(c.contents[-1])
        self.assertAlmostEqual(theta, 180)

    def test_flow_edges_accept_arrow_options(self):
        f = Flow(200, 400)
        f.addNode("a", 50, 100, ("circle", 20))
        f.addNode("b", 300, 100, ("circle", 20))
        f.addEdge("a", "b", directed="both", arrow_size=2, arrow_style="open")
        self.assertEqual(sum('#arrow_open' in e for e in f.contents), 2)
        f.addElbowEdge("a", "b", from_port="N", to_port="N", arrow_style="triangle")
        self.assertIn("#arrow_triangle", f.contents[-1])


class BezierFitTests(unittest.TestCase):
    def test_two_points_give_a_straight_third_split(self):
        a, b = Canvas(10, 10)._fitBezierCurve([(0, 0), (30, 0)])
        self.assertEqual([tuple(map(float, a[0])), tuple(map(float, b[0]))], [(10, 0), (20, 0)])

    def test_closed_curve_is_symmetric_and_smooth(self):
        pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
        a, b = Canvas(10, 10)._fitBezierCurve(pts, closed=True)
        n = len(pts)
        for i in range(n):
            # C1 at every knot, including the seam: a_i + b_{i-1} = 2 P_i
            np.testing.assert_allclose(np.add(a[i], b[i - 1]), np.multiply(pts[i], 2), atol=1e-9)
        # square symmetry: every handle has the same length
        lengths = {round(float(np.hypot(*np.subtract(a[i], pts[i]))), 6) for i in range(n)}
        self.assertEqual(len(lengths), 1)

    def test_open_curve_is_c2(self):
        pts = [(0, 0), (40, 30), (90, 10), (120, 60), (160, 40)]
        a, b = Canvas(10, 10)._fitBezierCurve(pts)
        for i in range(1, len(pts) - 1):
            np.testing.assert_allclose(np.add(a[i], b[i - 1]), np.multiply(pts[i], 2), atol=1e-9)
            # second derivatives match: P_i - 2 b_{i-1} + a_{i-1} == a_{i+1}... use explicit form
            left = np.subtract(np.add(pts[i], a[i - 1]), np.multiply(b[i - 1], 2))
            right = np.subtract(np.add(pts[i], b[i]), np.multiply(a[i], 2))
            np.testing.assert_allclose(left, right, atol=1e-9)


if __name__ == "__main__":
    unittest.main()

