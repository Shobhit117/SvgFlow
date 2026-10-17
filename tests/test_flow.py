import os
import re
import tempfile
import unittest

from svgflow import Canvas, Flow, Plot


def _orthogonal(points):
    return all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:]))


class ElbowEdgeTests(unittest.TestCase):
    def setUp(self):
        self.f = Flow(400, 600)
        self.f.addNode("a", 100, 100, ("rectangle", 40, 80))
        self.f.addNode("b", 400, 250, ("rectangle", 40, 80))

    def test_auto_ports_give_z_shape(self):
        pts = self.f.addElbowEdge("a", "b")
        self.assertEqual(pts[0], (140.0, 100.0))   # E port of a
        self.assertEqual(pts[-1], (360.0, 250.0))  # W port of b
        self.assertEqual(len(pts), 4)
        self.assertTrue(_orthogonal(pts))

    def test_same_side_ports_give_u_shape(self):
        # The user's example: leave and re-enter from the same side.
        pts = self.f.addElbowEdge("a", "b", from_port="W", to_port="W", stub=20)
        self.assertEqual(len(pts), 4)
        self.assertAlmostEqual(pts[1][0], 40.0)  # min(60, 360) - 20
        self.assertTrue(_orthogonal(pts))

    def test_perpendicular_ports_give_l_shape(self):
        pts = self.f.addElbowEdge("a", "b", from_port="E", to_port="N")
        self.assertEqual(pts, [(140.0, 100.0), (400.0, 100.0), (400.0, 230.0)])

    def test_target_behind_routes_around(self):
        pts = self.f.addElbowEdge("b", "a", from_port="E", to_port="W")
        self.assertTrue(_orthogonal(pts))
        self.assertGreater(pts[1][0], pts[0][0])    # leaves eastward first
        self.assertLess(pts[-2][0], pts[-1][0])     # enters a moving east

    def test_vertical_ports(self):
        self.f.addNode("c", 100, 300, ("circle", 20))
        pts = self.f.addElbowEdge("a", "c", from_port="S", to_port="N")
        self.assertEqual(pts, [(100.0, 120.0), (100.0, 280.0)])

    def test_waypoints_and_label_and_arrow(self):
        self.f.addElbowEdge("a", "b", waypoints=[(250, 100), (250, 250)], label="go & see")
        joined = "\n".join(self.f.contents)
        self.assertIn('xlink:href="#arrow"', joined)
        self.assertIn("go &amp; see", joined)

    def test_rounded_corners_use_quadratic_segments(self):
        self.f.addElbowEdge("a", "b", corner_radius=8)
        self.assertIn(" Q", self.f.contents[-2])
        self.f.addElbowEdge("a", "b", corner_radius=0, directed=False)
        self.assertNotIn(" Q", self.f.contents[-1])


class BugFixTests(unittest.TestCase):
    def test_polygon_y_has_four_decimals(self):
        c = Canvas(10, 10)
        c.addPolygon([(1, 2), (3, 4), (5, 6)])
        self.assertIn("1.0000,2.0000", c.contents[-1])

    def test_curved_line_zero_curvature_forwards_arrow_size(self):
        c = Canvas(10, 10)
        c.addCurvedLine(0, 0, 10, 0, 0, directed=True, arrow_size=3)
        self.assertIn("scale(3.0000 3.0000)", c.contents[-1])

    def test_legend_is_sorted(self):
        p = Plot(100, 100)
        p.addScatter([0.5], [0.5], label="scat") if hasattr(p, "addScatter") else p.legend_items.append(("scat", {"type": "scatter", "marker_type": "circle", "color": "red"}))
        p.addPlot([0, 1], [0, 1], label="line")
        p.addLegend(position=(10, 10))
        self.assertEqual([x[1]["type"] for x in p.legend_items], ["plot", "scatter"])

    def test_gradient_int_id(self):
        c = Canvas(10, 10)
        c.defineLinearGradient(1)
        self.assertEqual(c.getGradient(1), "url(#grad_1)")

    def test_parallelogram_both_spellings(self):
        f = Flow(200, 200)
        f.addNode("p", 100, 100, ("parallelogram", 80, 60, 60))
        f.addNode("q", 300, 100, ("paralellogram", 80, 60, 60))
        self.assertEqual(f.nodes["p"]["type"], "parallelogram")
        self.assertEqual(f.nodes["q"]["type"], "parallelogram")
        f.addEdge("p", "q")  # boundary intersection must still work


if __name__ == "__main__":
    unittest.main()
