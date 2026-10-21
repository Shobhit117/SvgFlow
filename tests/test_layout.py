import re
import unittest
import warnings

from svgflow import Figure, Plot, PlotStyle
from svgflow.text_metrics import text_width


def _translate(svg_element: str) -> tuple[float, float]:
    match = re.search(r'translate\(([-0-9.]+) ([-0-9.]+)\)', svg_element)
    return float(match.group(1)), float(match.group(2))


class TickSpacingTests(unittest.TestCase):
    def test_x_tick_gap_scales_with_font_size(self):
        for size in (10, 20):
            p = Plot(300, 300, origin=(50, 250), margins=(20, 20))
            p.addTicksX([(0.5, "a")], text_size=size, notch_length=10)
            _, y = _translate(p.contents[0])
            self.assertAlmostEqual(y, 250 + 5 + 0.35 * size, places=3)

    def test_y_tick_label_ends_left_of_notch(self):
        p = Plot(300, 300, origin=(80, 250), margins=(20, 20))
        p.addTicksY([(0.5, "123")], text_size=16, notch_length=10)
        x, _ = _translate(p.contents[0])
        self.assertAlmostEqual(x, 80 - 5 - 0.35 * 16, places=3)
        self.assertIn('text-anchor="end"', p.contents[0])

    def test_rotated_x_ticks_are_anchored_at_the_tick(self):
        p = Plot(300, 300, origin=(50, 250), margins=(20, 20))
        p.addTicksX([(0.5, "label")], rotation=-45, grid=False)
        self.assertIn('text-anchor="end"', p.contents[0])
        n = len(p.contents)
        p.addTicksX([(0.5, "label")], rotation=45, grid=False)
        self.assertIn('text-anchor="start"', p.contents[n])

    def test_y_axis_label_clears_the_widest_tick_label(self):
        style = PlotStyle()
        p = Plot(400, 400, origin=(150, 350), margins=(20, 20), style=style)
        p.addTicksY([(0.0, "0"), (1.0, "1,000,000")], notch_length=10)
        p.addAxisLabels(ylabel="Y")
        x, _ = _translate(p.contents[-1])
        widest = text_width("1,000,000", style.tick_size)
        # centre line = axis - (notch/2 + tick pad + widest + label pad + half label height)
        expected = 150 - (5 + 0.35 * 16 + widest + 0.5 * 16 + 0.5 * 16)
        self.assertAlmostEqual(x, expected, places=3)

    def test_x_axis_label_sits_below_tick_labels(self):
        p = Plot(400, 400, origin=(60, 300), margins=(20, 20))
        p.addTicksX([(0.5, "a")], notch_length=10)
        p.addAxisLabels(xlabel="X")
        _, y = _translate(p.contents[-1])
        self.assertAlmostEqual(y, 300 + 5 + 0.35 * 16 + 16 + 0.5 * 16, places=3)

    def test_label_outside_canvas_warns(self):
        p = Plot(200, 200, origin=(60, 190), margins=(20, 20))
        p.addTicksX([(0.5, "a")])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            p.addAxisLabels(xlabel="X")
        self.assertTrue(any("below the canvas" in str(w.message) for w in caught))


class AutoMarginTests(unittest.TestCase):
    def test_auto_margins_grow_with_fonts_and_tick_width(self):
        small = Plot(400, 600, origin="auto", margins="auto", style=PlotStyle.scaled(10))
        large = Plot(400, 600, origin="auto", margins="auto", style=PlotStyle.scaled(20))
        self.assertLess(small.O_x, large.O_x)
        self.assertGreater(small.O_y, large.O_y)
        self.assertLess(small.m_y, large.m_y)
        wide = Plot(400, 600, origin="auto", margins="auto", y_range=(0, 100000))
        narrow = Plot(400, 600, origin="auto", margins="auto", y_range=(0, 1))
        self.assertGreater(wide.O_x, narrow.O_x)

    def test_extra_margins_are_added(self):
        base = Plot(400, 600, origin="auto", margins="auto")
        more = Plot(400, 600, origin="auto", margins="auto", extra_margins=(1, 2, 3, 4))
        self.assertAlmostEqual(more.O_x - base.O_x, 1)
        self.assertAlmostEqual(base.O_y - more.O_y, 2)
        self.assertAlmostEqual(more.m_x - base.m_x, 3)
        self.assertAlmostEqual(more.m_y - base.m_y, 4)

    def test_auto_is_default_and_none_restores_legacy(self):
        self.assertEqual(Plot(400, 600).O_x, Plot(400, 600, origin="auto", margins="auto").O_x)
        p = Plot(100, 200, origin=None, margins=None)
        self.assertEqual((p.O_x, p.O_y, p.m_x, p.m_y), (30, 85, 20, 10))

    def test_too_small_canvas_falls_back_with_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            p = Plot(40, 40)
        self.assertTrue(any("too small" in str(w.message) for w in caught))
        self.assertEqual((p.O_x, p.O_y, p.m_x, p.m_y), (6, 34, 4, 4))


class FigureTests(unittest.TestCase):
    def test_grid_geometry(self):
        fig = Figure(220, 330, rows=2, cols=3, padding=10, wspace=5, hspace=0)
        # cell width = (330 - 20 - 10) / 3 = 100, cell height = (220 - 20) / 2 = 100
        self.assertEqual(fig.cellBox(0, 0), (10, 10, 100, 100))
        self.assertEqual(fig.cellBox(1, 2), (220, 110, 100, 100))
        self.assertEqual(fig.cellBox(0, 1, rowspan=2, colspan=2), (115, 10, 205, 200))

    def test_ratios(self):
        fig = Figure(100, 400, rows=1, cols=2, padding=0, wspace=0, width_ratios=(1, 3))
        self.assertEqual(fig.cellBox(0, 0)[2], 100)
        self.assertEqual(fig.cellBox(0, 1)[2], 300)

    def test_subplot_sizes_and_overlap(self):
        fig = Figure(600, 900, rows=2, cols=2)
        ax = fig.subplot(0, 0, colspan=2)
        x, y, w, h = fig.cellBox(0, 0, colspan=2)
        self.assertEqual((ax.width, ax.height), (w, h))
        with self.assertRaises(ValueError):
            fig.subplot(0, 1)
        with self.assertRaises(IndexError):
            fig.subplot(2, 0)

    def test_subplots_share_aligned_plot_areas(self):
        fig = Figure(600, 900, rows=2, cols=2)
        axes = fig.subplots()
        origins = {(a.O_x, a.O_y, a.m_x, a.m_y) for row in axes for a in row}
        self.assertEqual(len(origins), 1)

    def test_render_translates_and_uniquifies_ids(self):
        fig = Figure(400, 800, rows=1, cols=2, title="T")
        for c in range(2):
            ax = fig.subplot(0, c)
            ax.addLine(0, 0, 10, 10, directed=True)
            ax.addScatterPlot([0.5], [0.5], marker_type="cross")
        fig.addText("annotation", 10, 10)
        svg = fig.toSvg()
        for i in range(2):
            self.assertIn(f'id="sp{i}_arrow"', svg)
            self.assertIn(f'xlink:href="#sp{i}_cross"', svg)
        self.assertNotIn('id="arrow"', svg)
        x1, _, _, _ = fig.cellBox(0, 1)
        self.assertIn(f'<g transform="translate({x1:.4f}', svg)
        # Figure-level content added after the subplots is drawn on top of them.
        self.assertGreater(svg.index("annotation"), svg.rindex("sp1_cross"))

    def test_map_to_figure(self):
        fig = Figure(400, 800, rows=1, cols=2)
        fig.subplot(0, 0)
        ax = fig.subplot(0, 1, x_range=(0, 10), y_range=(0, 10))
        x, y, _, _ = fig.cellBox(0, 1)
        lx, ly = ax.mapToCanvas(5, 5)
        self.assertEqual(fig.mapToFigure(ax, 5, 5), (x + lx, y + ly))
        with self.assertRaises(KeyError):
            fig.mapToFigure(Plot(10, 10, origin=None, margins=None), 0, 0)

    def test_axis_arrowheads_clear_max_ticks_and_grid(self):
        for arrow_style in ("curved", "open", "triangle", "stealth"):
            for thickness in (1, 2, 4):
                p = Plot(400, 600, style=PlotStyle.scaled(14), extra_margins=(0, 0, 12, 12))
                p.easyAxes(thickness=thickness, grid=True, arrow_style=arrow_style)
                head_len = p._arrowLength(thickness, 1, arrow_style)
                x_tip = p.width - p.m_x + p._axisOverhang(True, thickness, 1, arrow_style)
                y_tip = p.m_y - p._axisOverhang(True, thickness, 1, arrow_style)
                # Rear of the arrowhead is at tip - head_len == plot boundary + axis_gap.
                self.assertAlmostEqual((x_tip - head_len) - (p.width - p.m_x), p.style.axis_gap)
                self.assertAlmostEqual(p.m_y - (y_tip + head_len), p.style.axis_gap)
                self.assertGreater(p.style.axis_gap, 0)

    def test_auto_margins_keep_directed_axes_on_canvas(self):
        p = Plot(300, 500, style=PlotStyle(outer_pad=2))
        x_end = p.width - p.m_x + p._axisOverhang(True, 2)
        y_end = p.m_y - p._axisOverhang(True, 2)
        self.assertLessEqual(x_end, p.width)
        self.assertGreaterEqual(y_end, 0)

    def test_axes_warn_when_explicit_margins_clip_arrowheads(self):
        p = Plot(300, 500, origin=(60, 250), margins=(5, 5))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            p.addAxes(thickness=2, directed=True)
        self.assertTrue(any("arrowheads extend past the canvas" in str(w.message) for w in caught))


if __name__ == "__main__":
    unittest.main()
