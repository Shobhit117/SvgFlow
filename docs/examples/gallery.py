"""Rebuild the guide's SVG figures: python docs/examples/gallery.py.

Requires an installed SvgFlow checkout. Outputs are relative to this file,
so running from another working directory is safe. No external tools needed.
"""
from pathlib import Path

import numpy as np
from svgflow import Canvas, Figure, Flow, FlowStyle, Plot, PlotStyle

OUTPUT = Path(__file__).resolve().parents[1] / "figures"
BLUE, TEAL, ORANGE = "#2563eb", "#0f766e", "#c2410c"


def background(canvas):
    """Give a canvas an opaque white background (``background=`` option)."""
    canvas.background = "white"
    return canvas


def save(canvas, name):
    """Save a named guide figure, creating the output directory if needed."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT / f"{name}.svg")


def hello():
    """Make the getting-started drawing."""
    c = background(Canvas(height=150, width=300))
    c.addRectangle(90, 220, 40, 30, color="aliceblue", border="steelblue",
                   thickness=2, corner_radius=12)
    c.addText("Hello, SvgFlow!", 150, 75, size=22, color="navy")
    save(c, "hello")


def coordinates():
    """Show coordinates and primitive reference points."""
    c = background(Canvas(290, 700))
    c.addText("SVG: origin at top-left, y increases downward", 350, 24, size=20)
    c.addLine(45, 65, 645, 65, directed=True, color=BLUE, thickness=2)
    c.addLine(45, 65, 45, 250, directed=True, color=BLUE, thickness=2)
    c.addText("(0, 0)", 38, 45, anchor="start", size=14)
    c.addText("+x", 665, 65, color=BLUE)
    c.addText("+y", 45, 270, color=BLUE)
    c.addRectangle(90, 150, 130, 120, color="aliceblue", border=BLUE, thickness=2)
    c.addCircle(130, 120, 4, color=ORANGE, border="none")
    c.addText("rectangle: top-left", 205, 230, size=15)
    c.addCircle(430, 165, 45, color="honeydew", border=TEAL, thickness=2)
    c.addCircle(430, 165, 4, color=ORANGE, border="none")
    c.addText("circle: center", 430, 230, size=15)
    c.addCircularArc(590, 150, 40, 0, 90, color=ORANGE, directed=True, thickness=2)
    c.addText("90 degrees", 590, 230, size=15)
    save(c, "coordinates")


def shapes():
    """Draw the basic filled primitives."""
    c = background(Canvas(230, 760))
    c.addText("Basic shapes", 380, 25, size=22)
    c.addRectangle(80, 120, 30, 70, color="aliceblue", border=BLUE, thickness=2, corner_radius=12)
    c.addCircle(255, 110, 42, color="honeydew", border=TEAL, thickness=2)
    c.addEllipse(430, 110, 68, 32, color="lemonchiffon", border=ORANGE, thickness=2, rotation=-15)
    c.addPolygon([(585, 75), (675, 65), (720, 125), (625, 155)], color="lavender", border="purple", thickness=2)
    for x, label in [(90, "rectangle"), (255, "circle"), (430, "ellipse"), (650, "polygon")]:
        c.addText(label, x, 190)
    save(c, "shapes")


def paths():
    """Compare straight, quadratic, cubic and fitted paths with controls."""
    c = background(Canvas(550, 760))
    c.addText("Paths: points and control handles", 380, 25, size=22)
    rows = [(95, "polyline"), (220, "quadratic"), (350, "cubic"), (485, "fitted spline")]
    for y, label in rows:
        c.addText(label, 25, y, anchor="start", size=15)
    c.addLinePath([(190, 95), (320, 65), (450, 115), (700, 95)], color=BLUE, thickness=3)
    ends = [(190, 220), (700, 220)]
    control = (445, 145)
    c.addLinePath([ends[0], control, ends[1]], color="silver", dashed=True)
    c.addQuadraticPath(ends, [control], color=TEAL, thickness=3)
    c.addCircle(*control, 4, color=ORANGE, border="none")
    p, q = (190, 350), (700, 350)
    a, b = (330, 285), (560, 410)
    c.addLine(*p, *a, color="silver", dashed=True)
    c.addLine(*b, *q, color="silver", dashed=True)
    c.addCubicPath([p, q], [a], [b], color=ORANGE, thickness=3)
    for pt in [a, b]:
        c.addCircle(*pt, 4, color=ORANGE, border="none")
    knots = [(190, 485), (330, 450), (480, 510), (700, 475)]
    c.addCurve(knots, color="purple", thickness=3)
    for pt in knots:
        c.addCircle(*pt, 4, color="purple", border="none")
    save(c, "paths")


def arrows():
    """Show all arrow styles, start/end heads and curve arrows."""
    c = background(Canvas(300, 760))
    c.addText("Arrow styles and direction", 380, 25, size=22)
    for i, style in enumerate(["curved", "open", "triangle", "stealth"]):
        y = 75 + i * 55
        c.addText(style, 25, y, anchor="start")
        c.addLine(150, y, 350, y, directed="both", arrow_style=style, color=BLUE, thickness=3)
        c.addCurvedLine(440, y + 10, 700, y + 10, 45, directed=True,
                        arrow_style=style, color=TEAL, thickness=2)
    save(c, "arrows")


def gradients():
    """Draw linear and radial object-bounding-box gradients."""
    c = background(Canvas(240, 700))
    c.addText("Linear and radial gradients", 350, 25, size=22)
    c.defineLinearGradient("sunset", x2=1, y2=1, stop_points=(0, 0.5, 1),
                           stop_colors=("gold", "tomato", "purple"))
    c.defineRadialGradient("glow", fx=0.35, fy=0.35, stop_colors=("white", "royalblue"))
    c.addRectangle(130, 300, 35, 65, color=c.getGradient("sunset"), border="none", corner_radius=16)
    c.addEllipse(520, 130, 130, 65, color=c.getGradient("glow"), border="none")
    c.addText("linear: diagonal", 185, 218)
    c.addText("radial: shifted focus", 520, 218)
    save(c, "gradients")


def text():
    """Show anchors, block alignment and word wrapping."""
    c = background(Canvas(380, 760))
    c.addText("Text alignment and wrapping", 380, 25, size=22)
    for x, anchor in [(130, "start"), (380, "middle"), (630, "end")]:
        c.addLine(x, 60, x, 160, color="silver", dashed=True)
        c.addText(["Alpha & beta", "Second line"], x, 105, anchor=anchor, size=18)
        c.addText(f'anchor="{anchor}"', x, 180, size=14)
    c.addRectangle(125, 270, 35, 220, color="aliceblue", border=BLUE)
    w, h = c.addText("Text wraps at word boundaries using measured font advances.",
                     50, 235, size=17, anchor="start", baseline="hanging", max_width=235)
    c.addText(f"measured block: {w:.0f} x {h:.0f}", 440, 250, anchor="start", size=15)
    c.addText("serif italic", 520, 295, font="serif", style="italic", size=24)
    c.addText("mono bold", 520, 340, font="mono", weight="bold", size=22)
    save(c, "text")


def sine():
    """Plot a sine curve with samples, legend and mapped annotation."""
    p = background(Plot(410, 700, style=PlotStyle.scaled(14),
                         x_range=(0, 2 * np.pi), y_range=(-1.2, 1.2)))
    x = np.linspace(0, 2 * np.pi, 81)
    p.easyAxes(grid=True)
    p.addPlot(x, np.sin(x), color=BLUE, thickness=3, label="sin(x)")
    p.addScatterPlot(x[::8], np.sin(x[::8]), color=ORANGE, marker_scale=0.7, label="samples")
    p.addAxisLabels("Angle (radians)", "Amplitude")
    p.addTitle("A line plot with sample markers")
    p.addLegend(anchor="NE", box_color="white", box_border_color="silver", box_opacity=0.95)
    save(p, "sine")


def custom_ticks():
    """Make category-like ticks with rotated labels and explicit margins."""
    p = background(Plot(380, 700, style=PlotStyle.scaled(13),
                         x_range=(-0.5, 3.5), y_range=(0, 100), extra_margins=(0, 50, 0, 0)))
    p.addAxes()
    p.addTicksX(list(enumerate(["North region", "South region", "East region", "West region"])),
                rotation=-30, grid=False)
    p.addTicksY([(0, "0%"), (25, "25%"), (50, "50%"), (75, "75%"), (100, "100%")])
    p.addBarPlot([0, 1, 2, 3], [65, 85, 52, 74], bar_width=60, color=TEAL)
    p.addAxisLabels("Region", "Completion")
    p.addTitle("Custom tick labels")
    save(p, "custom-ticks")


def grid():
    """Create a two-row figure with a spanning bottom subplot."""
    f = background(Figure(670, 960, rows=2, cols=2, title="A grid with a spanning subplot",
                          style=PlotStyle.scaled(12), wspace=25, hspace=30, padding=18))
    x = np.linspace(0, 6, 50)
    for col, func in enumerate([np.sin, np.cos]):
        ax = f.subplot(0, col, x_range=(0, 6), y_range=(-1.2, 1.2))
        ax.easyAxes(grid=True)
        ax.addPlot(x, func(x), color=[BLUE, TEAL][col], thickness=2)
        ax.addAxisLabels("Time", "Signal")
        ax.addTitle(func.__name__)
    ax = f.subplot(1, 0, colspan=2, x_range=(0, 6), y_range=(0, 1.1))
    ax.easyAxes(grid=True)
    ax.addPlot(x, np.exp(-x / 2), color=ORANGE, thickness=3)
    ax.addAxisLabels("Time", "Magnitude")
    ax.addTitle("One plot spans both columns")
    px, py = f.mapToFigure(ax, 3, np.exp(-1.5))
    f.addLine(px + 100, py - 45, px + 8, py - 4, directed=True, color=ORANGE)
    f.addText("figure annotation", px + 100, py - 60, size=13)
    save(f, "grid")


def nodes():
    """Show every node shape and the port coordinate convention."""
    f = background(Flow(270, 800, style=FlowStyle(node_color="aliceblue", node_border=BLUE, text_size=15)))
    f.addText("Node shapes: every position is a center", 400, 25, size=22)
    for node_id, x, shape in [
        ("circle", 90, ("circle", 42)),
        ("rectangle", 280, ("rectangle", 75, 135, 12)),
        ("ellipse", 485, ("ellipse", 75, 40)),
        ("parallelogram", 690, ("parallelogram", 130, 100, 65)),
    ]:
        f.addNode(node_id, x, 115, shape=shape)
        f.addCircle(x, 115, 3, color=ORANGE, border="none")
        f.addText(node_id, x, 195, size=15)
    for port in ["N", "S", "E", "W"]:
        px, py = f.getPort("rectangle", port)
        f.addCircle(px, py, 4, color=ORANGE, border="none")
        dx, dy = {"N": (0, -16), "S": (0, 16), "E": (16, 0), "W": (-16, 0)}[port]
        f.addText(port, px + dx, py + dy, size=12, color=ORANGE)
    f.addText("Orange dots: centers and N/S/E/W port positions", 400, 245, size=15)
    save(f, "nodes")


def pipeline():
    """Draw straight/curved/elbow edges and a self-loop in a workflow."""
    style = FlowStyle(node_shape=("rectangle", 60, 125, 10), node_color="aliceblue",
                      node_border=BLUE, edge_color=TEAL, arrow_style="stealth", text_size=16,
                      edge_text_size=14)
    f = background(Flow(380, 850, style=style))
    f.addText("A workflow with explicit routing", 425, 28, size=22)
    f.addNode("load", 110, 145, label="Load", shape=("ellipse", 65, 32))
    f.addNode("check", 365, 145, label="Validate")
    f.addNode("done", 700, 145, label="Publish", color="honeydew", border=TEAL)
    f.addNode("repair", 365, 290, label="Repair", color="lemonchiffon", border=ORANGE)
    f.addEdge("load", "check", directed=True, label="input")
    f.addEdge("check", "done", directed=True, label="valid")
    f.addElbowEdge("check", "repair", from_port="S", to_port="N", label="invalid")
    f.addElbowEdge("repair", "load", from_port="W", to_port="S", label="retry", corner_radius=12)
    f.addSelfEdge("done", theta1=240, theta2=300, curvature=70, directed=True, label="refresh")
    save(f, "pipeline")


def composition():
    """Build an icon, import it once and place transformed copies."""
    icon = Canvas(80, 100)
    icon.defineLinearGradient("paint", stop_colors=("royalblue", "teal"))
    icon.addRectangle(60, 80, 10, 10, color=icon.getGradient("paint"), border="none", corner_radius=10)
    icon.addLine(30, 40, 70, 40, color="white", thickness=3, directed=True, arrow_style="triangle")
    save(icon, "icon")
    c = background(Canvas(240, 720))
    c.addText("One SVG definition, multiple placements", 360, 25, size=22)
    c.importSvgFromFile(OUTPUT / "icon.svg", fig_id="icon")
    c.addSubFig("icon", 120, 120)
    c.addSubFig("icon", 340, 120, scale=1.3, rot=-20)
    c.addSubFig("icon", 590, 120, scale=0.9, flip=True)
    for x, label in [(120, "original"), (340, "scale + rotation"), (590, "horizontal flip")]:
        c.addText(label, x, 205, size=16)
    save(c, "composition")


def main():
    """Regenerate every core gallery figure."""
    for draw in [hello, coordinates, shapes, paths, arrows, gradients, text,
                 sine, custom_ticks, grid, nodes, pipeline, composition]:
        draw()
    print(f"Wrote 14 SVGs to {OUTPUT}")


if __name__ == "__main__":
    main()
