import os
import re
import tempfile
import unittest
from unittest.mock import patch

from svgflow import Canvas, Figure, Flow, Plot
from svgflow import external_figures


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

    def test_gradient_spread_method_and_opacity_validation(self):
        c = Canvas(10, 10)
        c.defineLinearGradient("lin", spread_method="reflect")
        c.defineRadialGradient("rad", spread_method="repeat")
        self.assertIn('spreadMethod="reflect"', c.defs[0])
        self.assertIn('spreadMethod="repeat"', c.defs[1])
        with self.assertRaises(ValueError):
            c.defineLinearGradient("bad_op", stop_points=(0, 1), stop_colors=("red", "blue"), stop_opacities=(-0.1, 1.0))

    def test_canvas_and_figure_background(self):
        c = Canvas(100, 200, background="white")
        c.addText("Hi", 50, 50)
        self.assertEqual(len(c.contents), 1)
        svg = c.toSvg()
        self.assertLess(svg.index('fill="white"'), svg.index("Hi"))

        fig = Figure(200, 300, rows=1, cols=1, title="Header", background="#f8fafc")
        fig.subplot(0, 0)
        fig_svg = fig.toSvg()
        self.assertLess(fig_svg.index('fill="#f8fafc"'), fig_svg.index("Header"))

    def test_latex_labels_and_title_forward_color(self):
        p = Plot(200, 300)
        calls = []
        with patch.object(p, "addLaTeX", side_effect=lambda *args, **kwargs: calls.append(kwargs.get("color"))):
            p.addAxisLabels("x", "y", color="navy", xlatex=True, ylatex=True)
            p.addTitle("T", color="teal", latex=True)
        self.assertEqual(calls, ["navy", "navy", "teal"])

    def test_tex2svg_in_memory_cache_uniquifies_per_eq_num(self):
        external_figures._compile_tex_svg.cache_clear()
        fake_svg = '<svg viewBox="0 0 20 10"><g id="g0"><use xlink:href="#g0"/></g></svg>'
        with patch.object(external_figures, "run") as mock_run, \
             patch.object(external_figures.Path, "read_text", return_value=fake_svg):
            svg1, w1, h1 = external_figures.tex2svg("x^2", eq_num=1)
            svg2, w2, h2 = external_figures.tex2svg("x^2", eq_num=2)
            # Only 2 subprocess calls (pdflatex + inkscape) for the first invocation; second hits cache
            self.assertEqual(mock_run.call_count, 2)
        self.assertIn('id="eq1_g0"', svg1)
        self.assertIn('id="eq2_g0"', svg2)
        self.assertEqual((w1, h1), (20.0, 10.0))
        external_figures._compile_tex_svg.cache_clear()

    def test_parallelogram_both_spellings(self):
        f = Flow(200, 200)
        f.addNode("p", 100, 100, ("parallelogram", 80, 60, 60))
        f.addNode("q", 300, 100, ("paralellogram", 80, 60, 60))
        self.assertEqual(f.nodes["p"]["type"], "parallelogram")
        self.assertEqual(f.nodes["q"]["type"], "parallelogram")
        f.addEdge("p", "q")  # boundary intersection must still work


class HighValueFeatureTests(unittest.TestCase):
    def test_nice_ticks_and_legacy_easy_ticks(self):
        ticks = Plot._niceTicks(0, 10, 6)
        self.assertEqual(ticks, [(0.0, "0"), (2.0, "2"), (4.0, "4"), (6.0, "6"), (8.0, "8"), (10.0, "10")])
        frac_ticks = Plot._niceTicks(0, 1, 5)
        self.assertEqual(frac_ticks, [(0.0, "0"), (0.25, "0.25"), (0.5, "0.5"), (0.75, "0.75"), (1.0, "1")])

        p_nice = Plot(300, 500, x_range=(0, 7), y_range=(0, 10))
        p_nice.easyAxes()
        svg_nice = p_nice.toSvg()
        self.assertNotIn(".00<", svg_nice)
        self.assertIn(">5<", svg_nice)

        p_legacy = Plot(300, 500, x_range=(0, 7), y_range=(0, 10))
        p_legacy.easyAxes(nice=False)
        svg_legacy = p_legacy.toSvg()
        self.assertIn(".00<", svg_legacy)

    def test_negative_bars_and_bar_options(self):
        p = Plot(300, 400, x_range=(0, 4), y_range=(-5, 5))
        p.addBarPlot([1, 2, 3], [3, -4, 2], _y=0, bar_width=24, border="black", corner_radius=3, label="delta")
        rects = [line for line in p.contents if line.startswith("<rect")]
        self.assertEqual(len(rects), 3)
        for r in rects:
            m = re.search(r'height="([-0-9.]+)"', r)
            self.assertIsNotNone(m)
            self.assertGreater(float(m.group(1)), 0.0)
            self.assertIn('rx="3"', r)

    def test_horizontal_bar_and_gantt_chart(self):
        p = Plot(320, 600, x_range=(0, 12), y_range=(0, 4))
        tasks = [
            ("Spec", 0, 3, "#2563eb", 1.0),
            {"task": "Build", "start": 2, "duration": 5, "color": "#0f766e", "progress": 0.6, "text": "60%"},
            ("Verify", 6, 10, "#d97706"),
            ("Launch", 10, 10, "#dc2626"),  # milestone (start == end)
        ]
        p.addGantt(tasks, show_durations=True, label="Schedule")
        svg = p.toSvg()
        self.assertIn("Spec", svg)
        self.assertIn("Build", svg)
        self.assertIn("60%", svg)
        self.assertIn("<polygon", svg)  # milestone diamond
        self.assertEqual(len(p.legend_items), 1)

    def test_box_plot_from_samples_and_dicts(self):
        p = Plot(320, 500, x_range=(0, 4), y_range=(0, 20))
        samples = [
            [2, 4, 5, 5, 6, 6, 7, 8, 19],  # 19 is an outlier
            {"q1": 6, "median": 9, "q3": 12, "whislo": 3, "whishi": 15, "fliers": [1, 18], "mean": 9.2},
            [8, 9, 10, 10, 11, 12, 13],
        ]
        p.addBoxPlot(
            samples,
            positions=[1, 2, 3],
            color="cycle",
            show_outliers=True,
            show_means=True,
            labels=["A", "B", "C"],
            label="Distributions",
        )
        svg = p.toSvg()
        self.assertIn(">A<", svg)
        self.assertIn(">B<", svg)
        self.assertIn(">C<", svg)
        self.assertTrue(any(line.startswith("<circle") for line in p.contents))
        self.assertEqual(len(p.legend_items), 1)

    def test_fill_between_and_reference_lines(self):
        p = Plot(300, 400, x_range=(0, 10), y_range=(-2, 10))
        p.addFillBetween([0, 5, 10], [2, 6, 4], [1, 3, 2], label="Band")
        p.addHLine(0, color="gray", dashed=True, label="Zero")
        p.addVLine(5, color="crimson", dashed=True, label="Split")
        p.addLegend()
        svg = p.toSvg()
        self.assertIn("<polygon", svg)
        self.assertIn("Band", svg)
        self.assertIn("Zero", svg)
        self.assertIn("Split", svg)

    def test_step_plots_and_error_bars(self):
        p = Plot(300, 400, x_range=(0, 4), y_range=(0, 10))
        for mode in ("post", "pre", "mid"):
            p.addPlot([1, 2, 3], [2, 5, 3], step=mode)
        with self.assertRaises(ValueError):
            p.addPlot([1, 2], [2, 4], interp=True, step="post")
        with self.assertRaises(ValueError):
            p.addPlot([1, 2], [2, 4], step="invalid")

        p.addErrorBars([1, 2, 3], [2, 5, 3], yerr=[0.5, 1.0, 0.8], xerr=([0.1, 0.2, 0.1], [0.2, 0.3, 0.2]))
        svg = p.toSvg()
        self.assertIn("<path", svg)

    def test_diamond_and_stadium_flow_nodes(self):
        f = Flow(300, 500)
        f.addNode("start", 100, 150, ("stadium", 50, 120), label="Start")
        f.addNode("check", 300, 150, ("diamond", 80, 120), label="Valid?")
        self.assertEqual(f.getPort("start", "E"), (160.0, 150.0))
        self.assertEqual(f.getPort("start", "W"), (40.0, 150.0))
        self.assertEqual(f.getPort("check", "W"), (240.0, 150.0))
        self.assertEqual(f.getPort("check", "N"), (300.0, 110.0))
        self.assertEqual(f.getPort("check", "S"), (300.0, 190.0))
        # Diagonal intersection on diamond must satisfy |dx|/(w/2) + |dy|/(h/2) == 1
        px, py = f._getIntersectionWithContainer("check", 35)
        val = abs(px - 300.0) / 60.0 + abs(py - 150.0) / 40.0
        self.assertAlmostEqual(val, 1.0, places=6)
        f.addEdge("start", "check", directed=True)


if __name__ == "__main__":
    unittest.main()
