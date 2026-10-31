"""Rebuild the showcase figures: python -m docs.examples.showcase.

These are richer, publication-style compositions that combine several parts
of the library (themes, palettes, figures, bands, annotations, flow routing,
gradients). No external tools are needed. Outputs go to ``docs/figures``.
"""
import math
from pathlib import Path

import numpy as np
from svgflow.external_figures import uniquify_svg_ids
from svgflow import (FLOW_THEMES, PALETTES, Canvas, Figure, Flow, FlowStyle,
                     Plot, PlotStyle)

OUTPUT = Path(__file__).resolve().parents[1] / "figures"
INK, MUTED, GRID = "#0f172a", "#64748b", "#e2e8f0"
BLUE, ORANGE, TEAL, PURPLE = "#2563eb", "#c2410c", "#0f766e", "#7c3aed"


def save(canvas, name):
    """Save a showcase figure, creating the output folder if needed."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT / f"{name}.svg")


# --------------------------------------------------------------------------- #
# 1. Same mean, very different tail
# --------------------------------------------------------------------------- #
def binomial_pmf(n, p):
    """Binomial pmf computed in log space."""
    k = np.arange(n + 1)
    logp = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log(1 - p) for i in k]
    pmf = np.exp(logp)
    return k, pmf / pmf.sum()


def negbin_pmf(mean, r, max_x):
    """Negative binomial pmf parameterised by mean and size."""
    p = r / (r + mean)
    pmf = np.empty(max_x + 1)
    pmf[0] = p ** r
    for k in range(1, max_x + 1):
        pmf[k] = pmf[k - 1] * (k + r - 1) / k * (1 - p)
    return np.arange(max_x + 1), pmf / pmf.sum()


def quantile(x, pmf, alpha):
    """Smallest x whose cumulative probability reaches alpha."""
    return int(x[np.searchsorted(np.cumsum(pmf), alpha)])


def demand_tails():
    """Overlaid pmfs with mean/quantile markers and a callout arrow."""
    xn, pn = binomial_pmf(100, 0.5)
    xw, pw = negbin_pmf(50, 4, 300)
    qn, qw = quantile(xn, pn, 0.95), quantile(xw, pw, 0.95)
    ymax = 0.085
    p = Plot(500, 880, x_range=(0, 140), y_range=(0, ymax), background="white",
             style=PlotStyle.scaled(14), extra_margins=(0, 0, 10, 8))
    p.addAxes(thickness=2, directed=True)
    p.addTicksX([(v, str(v)) for v in range(0, 141, 20)], notch_thickness=1.5)
    p.addTicksY([(v, f"{v:.2f}") for v in np.arange(0, ymax, 0.02)], notch_thickness=1.5)
    for x, v in zip(xw, pw):
        if x <= 140 and v > 1.5e-4:
            p.addBar(x, v, 5.2, bar_color=ORANGE, opacity=0.5)
    for x, v in zip(xn, pn):
        if x <= 140 and v > 1.5e-4:
            p.addBar(x, v, 3.6, bar_color=BLUE, opacity=0.85)
    for value, color, text, frac in [(50, INK, "", 0.9), (qn, BLUE, f"95th pct = {qn}", 0.74),
                                     (qw, ORANGE, f"95th pct = {qw}", 0.62)]:
        p.addVLine(value, color=color, thickness=2, dashed=True)
        if text:
            x0, ty = p.mapToCanvas(value, ymax * frac)
            p.addText(text, x0 + 8, ty, color=color, anchor="start", size=14, weight="bold")
    xa, ya = p.mapToCanvas(qn, ymax * 0.5)
    xb, yb = p.mapToCanvas(qw, ymax * 0.5)
    p.addLine(xa, ya, xb, yb, color=MUTED, thickness=2, directed=True, arrow_style="stealth")
    p.addText([f"same mean, +{qw - qn} units", "at the 95% service level"],
              (xa + xb) / 2, ya + 30, color=MUTED, size=14, weight="bold")
    p.addAxisLabels("Demand during period", "Probability mass")
    p.addTitle(f"Same mean demand, very different tails ({qn} vs {qw})", size=19)
    # Hand-built legend: translucent bars cannot be registered automatically.
    lx, ly = p.mapToCanvas(88, ymax * 0.97)
    p.addRectangle(70, 250, lx, ly, color="white", border="silver", thickness=1.5,
                   opacity=0.95, corner_radius=8)
    for i, (text, color, op) in enumerate([("Narrow: Binomial(100, 0.5)", BLUE, 0.85),
                                           ("Lumpy: NegBin(mean 50, r=4)", ORANGE, 0.5)]):
        y = ly + 22 + 28 * i
        p.addRectangle(14, 26, lx + 14, y - 7, color=color, border="none", opacity=op)
        p.addText(text, lx + 50, y, anchor="start", size=13)
    save(p, "showcase-demand-tails")


# --------------------------------------------------------------------------- #
# 2. Multi-panel dashboard
# --------------------------------------------------------------------------- #
def dashboard():
    """A themed 2x2 figure mixing bands, bars, scatter and cumulative curves."""
    style = PlotStyle.theme("default", base_size=12)
    fig = Figure(640, 980, rows=2, cols=2, style=style, wspace=26, hspace=34, padding=18,
                 title="Experiment dashboard", background="white")
    rng = np.random.default_rng(7)

    # (a) damped oscillation with an uncertainty band
    a = fig.subplot(0, 0, x_range=(0, 10), y_range=(-1.2, 1.2))
    t = np.linspace(0, 10, 200)
    y = np.exp(-t / 5) * np.cos(2.2 * t)
    env = 0.12 + 0.05 * t / 10
    a.addAxes(directed=True)
    a.addTicksX([(v, str(v)) for v in range(0, 11, 2)], grid=True)
    a.addTicksY([(v, f"{v:g}") for v in (-1, -0.5, 0, 0.5, 1)], grid=True)
    c = a.nextColor()
    a.addFillBetween(t, y - env, y + env, color=c, opacity=0.16)
    a.addPlot(t, y, color=c, thickness=2.5, label="response")
    a.addPlot(t, np.exp(-t / 5), color=MUTED, thickness=1.5, dashed=True, label="envelope")
    a.addAxisLabels("Time (s)", "Amplitude")
    a.addTitle("Damped response \u00b1 band")
    a.addLegend(anchor="NE")

    # (b) grouped bars
    b = fig.subplot(0, 1, x_range=(-0.6, 3.6), y_range=(0, 100))
    cats = ["A", "B", "C", "D"]
    b.addAxes(directed=True)
    b.addTicksX(list(enumerate(cats)), grid=False)
    b.addTicksY([(v, str(v)) for v in range(0, 101, 25)])
    width = abs(b.mapToCanvas(0.3, 0)[0] - b.mapToCanvas(0, 0)[0])
    b.addBarPlot(np.arange(4) - 0.17, [62, 71, 55, 83], bar_width=width, label="baseline")
    b.addBarPlot(np.arange(4) + 0.17, [74, 80, 69, 91], bar_width=width, label="tuned")
    b.addAxisLabels("Group", "Score")
    b.addTitle("Grouped comparison")
    b.addLegend(anchor="NW")

    # (c) scatter with fitted line
    c_ax = fig.subplot(1, 0, x_range=(0, 10), y_range=(0, 30))
    xs = rng.uniform(0.3, 9.7, 45)
    ys = 2.4 * xs + 3 + rng.normal(0, 2.2, xs.size)
    slope, icpt = np.polyfit(xs, ys, 1)
    c_ax.addAxes(directed=True)
    c_ax.addTicksX([(v, str(v)) for v in range(0, 11, 2)])
    c_ax.addTicksY([(v, str(v)) for v in range(0, 31, 10)])
    c_ax.addScatterPlot(xs, ys, marker_scale=0.65, label="observations")
    c_ax.addPlot([0.2, 9.8], [icpt + slope * 0.2, icpt + slope * 9.8], thickness=2.5,
                 color=ORANGE, label=f"fit (slope {slope:.2f})")
    c_ax.addAxisLabels("Load", "Latency (ms)")
    c_ax.addTitle("Linear trend")
    c_ax.addLegend(anchor="SE")

    # (d) CDF curves with a threshold
    d = fig.subplot(1, 1, x_range=(0, 12), y_range=(0, 1))
    d.addAxes(directed=True)
    d.addTicksX([(v, str(v)) for v in range(0, 13, 3)])
    d.addTicksY([(v, f"{v:g}") for v in (0, 0.25, 0.5, 0.75, 1)])
    x = np.linspace(0, 12, 160)
    for k, label in [(1.5, "light"), (3, "medium"), (5, "heavy")]:
        d.addPlot(x, 1 - np.exp(-(x / k) ** 1.4), thickness=2.5, label=label)
    d.addHLine(0.95, color="firebrick", dashed=True, thickness=1.5)
    hx0, hy = d.mapToCanvas(0, 0.95)
    d.addText("95%", hx0 + 6, hy - 9, anchor="start", size=12, color="firebrick")
    d.addAxisLabels("Service time", "P(T \u2264 t)")
    d.addTitle("Cumulative distributions")
    d.addLegend(anchor="SE")
    save(fig, "showcase-dashboard")


# --------------------------------------------------------------------------- #
# 3. Architecture / training pipeline
# --------------------------------------------------------------------------- #
def pipeline():
    """A themed flow with gradient header, mixed shapes and routed edges."""
    style = FlowStyle.theme("ocean", node_shape=("rectangle", 58, 138, 12), text_size=15,
                            edge_text_size=13, node_thickness=2, edge_thickness=2)
    f = Flow(380, 940, style=style, background="white")
    f.defineLinearGradient("hdr", x2=1, y2=0, stop_colors=("#1d4ed8", "#0f766e"))
    f.addRectangle(54, 940, 0, 0, color=f.getGradient("hdr"), border="none")
    f.addText("Model training pipeline", 470, 27, color="white", size=22, weight="bold")

    f.addNode("data", 100, 150, shape=("ellipse", 76, 38), label="Raw data", color="lemonchiffon", border="#b45309")
    f.addNode("clean", 290, 150, label="Clean & split")
    f.addNode("feat", 480, 150, label="Features")
    f.addNode("train", 670, 150, label="Train", color="honeydew", border="#15803d")
    f.addNode("eval", 670, 290, label="Evaluate", color="honeydew", border="#15803d")
    f.addNode("ok", 480, 290, shape=("diamond", 76, 130), label="Pass?", color="lavender", border="#6d28d9")
    f.addNode("deploy", 290, 290, shape=("stadium", 56, 136), label="Deploy", color="#dcfce7", border="#15803d")
    f.addNode("tune", 840, 150, shape=("circle", 42), label="Tune", color="#fee2e2", border="#b91c1c")
    f.addEdge("data", "clean", directed=True, label="ingest")
    f.addEdge("clean", "feat", directed=True)
    f.addEdge("feat", "train", directed=True, label="X, y")
    f.addEdge("train", "eval", directed=True)
    f.addEdge("eval", "ok", directed=True, label="metrics")
    f.addEdge("ok", "deploy", directed=True, label="yes", color="#15803d")
    f.addEdge("train", "tune", directed=True, curvature=0, dashed=True, color="#b91c1c")
    f.addElbowEdge("ok", "feat", from_port="N", to_port="S", label="no: iterate", color="#b91c1c", dashed=True)
    f.addSelfEdge("tune", theta1=300, theta2=240, curvature=60, directed=True, label="grid", color="#b91c1c")
    f.addText("solid: main flow    dashed: feedback loops", 470, 355, color=MUTED, size=14)
    save(f, "showcase-pipeline")


# --------------------------------------------------------------------------- #
# 4. Palette and theme swatches
# --------------------------------------------------------------------------- #
def themes():
    """Show every built-in plot palette and flow theme side by side."""
    c = Canvas(700, 820, background="white")
    c.addText("Built-in palettes and flow themes", 410, 28, size=22, weight="bold")
    c.addText("PlotStyle.theme(name)  \u2014  series colors cycle in order", 410, 56, size=14, color=MUTED)
    for i, (name, colors) in enumerate(PALETTES.items()):
        y = 82 + i * 34
        c.addText(name, 20, y + 12, anchor="start", size=15, font="mono")
        for j, col in enumerate(colors):
            c.addRectangle(24, 50, 150 + j * 56, y, color=col, border="none", corner_radius=6)
    c.addText("FlowStyle.theme(name)", 410, 346, size=14, color=MUTED)
    names = list(FLOW_THEMES)
    for i, name in enumerate(names):
        col, row = i % 4, i // 4
        x0, y0 = 20 + col * 200, 380 + row * 150
        f = FlowStyle.theme(name, node_shape=("rectangle", 44, 76, 8), text_size=13, edge_text_size=11)
        sub = Flow(120, 190, style=f)
        sub.addNode("a", 50, 52, label="A")
        sub.addNode("b", 142, 52, label="B", shape=("circle", 22))
        sub.addEdge("a", "b", directed=True)
        sub.addText(name, 95, 108, size=14, font="mono")
        sid = f"theme{i}"
        c._defSubFigure(sid, (0, 0, 190, 120), uniquify_svg_ids(sub.toSvg(), sid))
        c.addSubFig(sid, x0, y0, anchor="start", baseline="hanging")
    save(c, "showcase-themes")


# --------------------------------------------------------------------------- #
# 5. Anatomy of a plot
# --------------------------------------------------------------------------- #
def anatomy():
    """Annotate the layout vocabulary used by PlotStyle and Plot."""
    style = PlotStyle.scaled(14)
    p = Plot(440, 760, x_range=(0, 10), y_range=(0, 100), style=style,
             background="white", extra_margins=(0, 0, 40, 10))
    p.addAxes(thickness=2, directed=True)
    p.addTicksX([(v, str(v)) for v in range(0, 11, 2)], grid=True)
    p.addTicksY([(v, str(v)) for v in range(0, 101, 25)], grid=True)
    x = np.linspace(0, 10, 100)
    p.addPlot(x, 55 + 30 * np.sin(x / 1.6), thickness=3, label="series")
    p.addAxisLabels("x label", "y label")
    p.addTitle("Title")
    p.addLegend(anchor="SE")

    def tag(text, x, y, tx, ty, anchor="start"):
        """Orange callout with a leader arrow to (x, y)."""
        p.addLine(tx, ty, x, y, color=ORANGE, thickness=1.5, directed=True, arrow_size=0.8)
        dx = 6 if anchor == "start" else -6
        p.addText(text, tx + dx, ty, color=ORANGE, anchor=anchor, size=13, weight="bold")

    ox, oy = p.O_x, p.O_y
    right, top = p.width - p.m_x, p.m_y
    p.addRectangle(oy - top, right - ox, ox, top, color="none", border=ORANGE, thickness=1.5, opacity=0.8)
    p.addCircle(ox, oy, 5, color=ORANGE, border="none")
    p.addCircle(right, top, 5, color=ORANGE, border="none")
    tag("origin (O_x, O_y)", ox, oy, ox + 60, oy + 46)
    tag("(width \u2212 m_x, m_y)", right, top, right - 20, top - 22, anchor="end")
    ext = p.tickExtent("y")
    y75, y38, y90 = (p.mapToCanvas(0, v)[1] for v in (75, 35, 92))
    tag("tick_pad", ox - style.tick_length / 2 - 3, y75, ox + 30, y90)
    tag("label_pad", ox - ext - 4, y38, ox + 30, y38 + 6)
    tag("title_pad", p.mapToCanvas(5, 100)[0] + 40, top - 8, p.mapToCanvas(5, 100)[0] + 90, top - 24)
    tag("axis_gap + arrowhead", right + 18, oy, right + 25, oy + 40, anchor="end")
    tag("outer_pad", 6, 6, 70, 26)
    save(p, "showcase-anatomy")


def main():
    """Regenerate every showcase figure."""
    for draw in (demand_tails, dashboard, pipeline, themes, anatomy):
        draw()
    print(f"Wrote 5 showcase SVGs to {OUTPUT}")


if __name__ == "__main__":
    main()
