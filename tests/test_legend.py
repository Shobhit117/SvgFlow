import re
import unittest

from svgflow import Plot
from svgflow.text_metrics import text_width


class LegendTests(unittest.TestCase):
    def _legend_width(self, label: str) -> float:
        plot = Plot(100, 100)
        plot.addPlot([0, 1], [0, 1], label=label)
        plot.addLegend(position=(10, 10))
        rectangle = plot.contents[-3]
        match = re.search(r'width="([0-9.]+)"', rectangle)
        self.assertIsNotNone(match)
        return float(match.group(1))

    def test_legend_width_depends_on_glyphs_not_character_count(self):
        self.assertGreater(self._legend_width("WWWW"), self._legend_width("iiii"))

    def test_legend_uses_measured_width_and_matching_font(self):
        label = "A wide legend"
        width = self._legend_width(label)
        self.assertAlmostEqual(width, text_width(label, 16) + 20, places=4)

        plot = Plot(100, 100)
        plot.addPlot([0, 1], [0, 1], label=label)
        plot.addLegend(position=(10, 10))
        legend_text = plot.contents[-2]
        self.assertIn('font-family="Helvetica, Arial, sans-serif"', legend_text)
        self.assertIn('lengthAdjust="spacingAndGlyphs"', legend_text)


if __name__ == "__main__":
    unittest.main()
