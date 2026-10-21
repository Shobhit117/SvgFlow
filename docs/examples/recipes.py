"""Runnable recipes from docs/recipes.md; no external programs required."""
from pathlib import Path

import numpy as np
from svgflow import Plot, PlotStyle

OUTPUT = Path(__file__).resolve().parents[1] / "figures"


def base_plot(x_range, y_range):
    """Create a consistently styled plot with an explicit white background."""
    p = Plot(390, 700, x_range=x_range, y_range=y_range, style=PlotStyle.scaled(14))
    p.addRectangle(p.height, p.width, 0, 0, color="white", border="none")
    return p


def save(p, name):
    """Write one recipe figure."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    p.save(OUTPUT / f"{name}.svg")


def uncertainty_band():
    """Fill an uncertainty band behind a curve using mapped polygon points."""
    x = np.linspace(0, 10, 60)
    mean = 3 + np.sin(x)
    low, high = mean - 0.5, mean + 0.5
    p = base_plot((0, 10), (0, 5))
    p.easyAxes(grid=True)
    boundary = list(zip(x, high)) + list(zip(x[::-1], low[::-1]))
    p.addPolygon([p.mapToCanvas(a, b) for a, b in boundary],
                  color="royalblue", border="none", opacity=0.18)
    p.addPlot(x, mean, color="royalblue", thickness=3, label="mean")
    p.addPlot([0, 10], [4.5, 4.5], color="firebrick", dashed=True, label="threshold")
    cx, cy = p.mapToCanvas(7.5, 3 + np.sin(7.5))
    p.addLine(cx - 35, cy + 45, cx - 3, cy + 7, directed=True, color="darkorange")
    p.addText("mapped annotation", cx - 35, cy + 60, size=13, color="darkorange")
    p.addAxisLabels("Time", "Response")
    p.addTitle("An uncertainty band and a threshold")
    p.addLegend(anchor="SW", box_color="white", box_border_color="silver", box_opacity=0.9)
    save(p, "uncertainty-band")


def grouped_bars():
    """Offset data x positions and convert data width to canvas units."""
    p = base_plot((-0.6, 3.6), (0, 10))
    p.addAxes()
    p.addTicksX(list(enumerate(["A", "B", "C", "D"])), grid=False)
    p.addTicksY([(i, str(i)) for i in range(0, 11, 2)])
    x = np.arange(4)
    width = abs(p.mapToCanvas(0.32, 0)[0] - p.mapToCanvas(0, 0)[0])
    p.addBarPlot(x - 0.18, [4, 6, 5, 8], bar_width=width, color="royalblue", label="baseline")
    p.addBarPlot(x + 0.18, [6, 7, 8, 9], bar_width=width, color="teal", label="improved")
    p.addAxisLabels("Category", "Score")
    p.addTitle("Grouped bars")
    p.addLegend(anchor="NW", box_color="white", box_border_color="silver", box_opacity=0.9)
    save(p, "grouped-bars")


def stacked_bars():
    """Stack bars using explicit per-bar baselines and top coordinates."""
    p = base_plot((-0.6, 3.6), (0, 15))
    p.addAxes()
    p.addTicksX(list(enumerate(["Q1", "Q2", "Q3", "Q4"])), grid=False)
    p.addTicksY([(i, str(i)) for i in [0, 3, 6, 9, 12, 15]])
    x = np.arange(4)
    lower = np.array([4, 6, 5, 8])
    upper = np.array([3, 2, 4, 3])
    p.addBarPlot(x, lower, bar_width=52, color="royalblue", label="product A")
    p.addBarPlot(x, lower + upper, _y=lower, bar_width=52, color="teal", label="product B")
    p.addAxisLabels("Quarter", "Units")
    p.addTitle("Stacked bars: top = baseline + component")
    p.addLegend(anchor="NW", box_color="white", box_border_color="silver", box_opacity=0.9)
    save(p, "stacked-bars")


if __name__ == "__main__":
    uncertainty_band()
    grouped_bars()
    stacked_bars()
    print(f"Wrote 3 recipe SVGs to {OUTPUT}")
