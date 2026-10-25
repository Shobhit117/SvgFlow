# SvgFlow

![SvgFlow](docs/logo/svgflow-wordmark.svg)

SvgFlow is a lightweight Python library for creating SVG drawings, plots, and
flow diagrams. Drawings are assembled with Python and saved as editable SVG;
optional integrations add LaTeX labels and PNG/PDF export.

## Detailed documentation

Start with the **[documentation guide](docs/README.md)** for a complete learning
path, illustrated tutorials, runnable examples, recipes, troubleshooting,
and the full API reference.

- [Getting started](docs/getting-started.md)
- [Drawing, paths, arrows, and gradients](docs/drawing.md)
- [Text and fonts](docs/text-and-fonts.md)
- [Plotting](docs/plotting.md) and [subplot grids](docs/figures.md)
- [Flow diagrams and routing](docs/flow-diagrams.md)
- [SVG composition, LaTeX, and export](docs/composition-and-export.md)
- [Practical recipes](docs/recipes.md) and [API reference](docs/README.md#api-reference)

## Features

- Basic SVG shapes, text, paths, curves, arrows, and gradients
- `Plot` helpers for axes, ticks, lines, scatter plots, bars, and legends
- `Figure` grids of subplots with spanning cells and aligned plot areas
- Font-aware, automatic spacing of tick labels, axis labels, and titles
- `Flow` helpers for connected nodes, directed edges, and self-edges
- SVG subfigure imports
- LaTeX labels through Inkscape, `dvisvgm`, or `pdf2svg`
- PNG and PDF export through Inkscape

## Requirements

- Python 3.10 or newer
- NumPy 1.23 or newer
- PyMuPDF 1.24.3 or newer (used for font-aware legend sizing)

The following external programs are optional:

- [Inkscape](https://inkscape.org/) for PNG/PDF export and the default
  LaTeX-to-SVG backend
- `pdflatex` for LaTeX rendering
- `dvisvgm` or `pdf2svg` when using the corresponding LaTeX backend

## Installation

Install the published package from PyPI:

```bash
python -m pip install svgflow
```

For local development, clone the repository and install it in editable mode:

```bash
git clone https://github.com/YOUR_USERNAME/SvgFlow.git
cd SvgFlow
python -m pip install -e .
```

Replace `YOUR_USERNAME` with the GitHub account that hosts the repository.

## Quick start

<!-- render: core -->
```python
from svgflow import Flow

diagram = Flow(height=140, width=440)

diagram.addNode(
    "source", 65, 70,
    shape=("circle", 35),
    label="Source",
    color="lightblue",
)
diagram.addNode(
    "result", 355, 70,
    shape=("rectangle", 70, 110),
    label="Result",
    color="lightgreen",
)
diagram.addEdge("source", "result", label="transform", directed=True)
diagram.save("flow.svg")
```

![Rendered flow example](docs/figures/readme-flow.svg)

The first `Canvas`, `Plot`, and `Flow` constructor argument is the height; the
second is the width. SVG coordinates start at the top-left corner.

## Tutorials

### 1. Build a drawing from shapes

`Canvas` is the base class. Drawing methods append elements in order, so later
elements appear on top of earlier ones.

<!-- render: core -->
```python
from svgflow import Canvas

canvas = Canvas(height=200, width=360)

canvas.addRectangle(
    height=100,
    width=240,
    x=70,
    y=75,
    color="aliceblue",
    border="steelblue",
    thickness=3,
    corner_radius=16,
)
canvas.addCircle(70, 125, radius=26, color="gold", border="orange")
canvas.addLine(
    96, 125, 280, 125,
    color="steelblue",
    thickness=3,
    directed=True,
    label="process",
)
canvas.addText("SvgFlow", 180, 35, size=24, weight="bold")
canvas.save("drawing.svg")
```

![Rendered drawing example](docs/figures/readme-drawing.svg)

Useful drawing methods include `addText`, `addMultiLineText`, `addLine`,
`addCurvedLine`, `addRectangle`, `addCircle`, `addEllipse`, `addPolygon`, and
the line, quadratic, cubic, and fitted-curve path helpers.

#### Arrows

Every stroked method (`addLine`, `addCurvedLine`, the path helpers,
`addCircularArc`, and all `Flow` edges) takes the same arrow options:

- `directed`: `True`/`"end"`, `"start"`, `"both"`, or `False`;
- `arrow_style`: `"curved"` (default), `"open"`, `"triangle"`, or `"stealth"`;
  set `canvas.arrow_style` once to change the default for a whole canvas;
- `arrow_size`: a multiplier on the default head size, which already grows
  with the line `thickness`.

The arrow tip lands exactly on the end point and the line is shortened so it
never pokes through the head. `addArrowhead(x, y, angle, ...)` draws a
standalone head.

<!-- render: core -->
```python
from svgflow import Canvas

canvas = Canvas(90, 420)
canvas.arrow_style = "stealth"
canvas.addLine(20, 60, 210, 60, thickness=3, directed="both")
canvas.addCircularArc(340, 60, 35, 200, 340, directed=True, arrow_style="open")
canvas.save("arrows.svg")
```

![Rendered arrows example](docs/figures/readme-arrows.svg)

### 2. Create a line and scatter plot

`Plot` maps data coordinates onto the SVG canvas. Set the visible data ranges
when creating it, then add axes and one or more data series.

<!-- render: core -->
```python
import numpy as np
from svgflow import Plot

x = np.linspace(0, 2 * np.pi, 40)
y = np.sin(x)

plot = Plot(
    height=420,
    width=640,
    x_range=(0, 2 * np.pi),
    y_range=(-1.2, 1.2),
)
plot.easyAxes(grid=True)
plot.addPlot(x, y, color="royalblue", thickness=3, label="sin(x)")
plot.addScatterPlot(
    x[::4], y[::4],
    color="crimson",
    marker_type="circle",
    label="samples",
)
plot.addAxisLabels("x", "y")
plot.addTitle("Sine wave")
plot.addLegend(anchor="NE", box_color="white", box_border_color="gray")
plot.save("sine.svg")
```

![Rendered sine example](docs/figures/readme-sine.svg)

Use `addTicksX` and `addTicksY` when you need complete control over tick values
and labels. `addBarPlot` adds vertical bars and can share a legend with line or
scatter series.

#### Text spacing

Gaps between plot elements are measured from the actual text and scale with
the font size, so you rarely need to set them by hand:

- tick labels sit `0.35 em` beyond the end of the tick notch;
- axis labels sit `0.5 em` beyond the outer edge of the *widest* tick label
  on that axis (call `addAxisLabels` after drawing ticks);
- the title sits `0.6 em` above the plot area;
- rotated x tick labels hang off their tick (anchored at their end or start)
  instead of overlapping the axis.

All sizes and gaps live in a `PlotStyle`. By default (`origin="auto"`,
`margins="auto"`) the plot margins are sized from those fonts; pass
`origin=None, margins=None` for the legacy percentage layout:

<!-- render: core -->
```python
from svgflow import Plot, PlotStyle

style = PlotStyle.scaled(12)  # ticks/labels 12px, title ~14px, tick length 7.5px
plot = Plot(300, 420, style=style, x_range=(0, 10), y_range=(0, 5000))
plot.easyAxes(ticks_per_unit=0.025)  # denser automatic ticks for a compact plot
plot.addAxisLabels("Time", "Value")
plot.addPlot([0, 3, 7, 10], [500, 1800, 3200, 4500], color="royalblue", thickness=2)
plot.addTitle("Scaled plot text")
plot.save("plot-style.svg")
```

![Rendered plot style example](docs/figures/readme-plot-style.svg)

`ticks_per_unit` controls automatic tick density per canvas unit. Here the
221-unit-high plot area gets six y labels, from 0 to 5000; the default `0.01`
would produce only the two endpoint labels. `PlotStyle.scaled()` adjusts
text and spacing, while tick density is configured separately.

`PlotStyle(tick_size, label_size, title_size, tick_length=..., tick_pad=...,
label_pad=..., title_pad=..., outer_pad=...)` exposes every knob, and each
method still accepts explicit `pad`/`xpad`/`ypad`/`text_size` overrides. If
something (e.g. long rotated tick labels) needs more room, add it with
`extra_margins=(left, bottom, right, top)`; SvgFlow warns when an axis label
would fall outside the canvas.

### 3. Arrange subplots in a grid

`Figure` splits a canvas into `rows` x `cols` cells. `subplot(row, col,
rowspan=1, colspan=1, ...)` returns an ordinary `Plot` that you draw on in its
own local coordinates. Subplots use automatic margins; common styles and
compatible tick-label widths give aligned plot areas. Use explicit shared
margins when exact alignment across very different ranges is needed.

<!-- render: core -->
```python
import numpy as np
from svgflow import Figure, PlotStyle

fig = Figure(520, 760, rows=2, cols=2, title="Signals and decay",
             style=PlotStyle.scaled(12), wspace=20, hspace=28, padding=14)
x = np.linspace(0, 2 * np.pi, 80)

for col, f in enumerate([np.sin, np.cos]):
    ax = fig.subplot(0, col, x_range=(0, 2 * np.pi), y_range=(-1.2, 1.2))
    ax.addAxes(directed=True, thickness=2)
    ax.addTicksX([(0, "0"), (np.pi, "pi"), (2 * np.pi, "2pi")], grid=False)
    # Manual ticks keep compact y axes readable; pairs are (value, label).
    ax.addTicksY([(-1, "-1"), (-0.5, "-0.5"), (0, "0"),
                  (0.5, "0.5"), (1, "1")], grid=False)
    ax.addPlot(x, f(x), color="royalblue", thickness=2)
    ax.addAxisLabels("x", "y")
    ax.addTitle(f.__name__)

wide = fig.subplot(1, 0, colspan=2, x_range=(0, 2 * np.pi), y_range=(0, 1.1))
wide.addAxes(directed=True, thickness=2)
wide.addTicksX([(0, "0"), (np.pi, "pi"), (2 * np.pi, "2pi")], grid=False)
wide.addTicksY([(0, "0"), (0.25, "0.25"), (0.5, "0.5"),
                (0.75, "0.75"), (1, "1")], grid=False)
wide.addPlot(x, np.exp(-x / 2), color="teal", thickness=2)
wide.addAxisLabels("Time", "Magnitude")
wide.addTitle("Exponential decay spans both columns")

# Map subplot data into figure coordinates for a figure-level annotation.
x1, y1 = fig.mapToFigure(wide, 3, np.exp(-1.5))
fig.addLine(x1 + 90, y1 - 35, x1 + 6, y1 - 4, directed=True, color="teal")
fig.addText("decay", x1 + 90, y1 - 48, size=13)
fig.save("grid.svg")
```

![Rendered grid example](docs/figures/readme-grid.svg)

Automatic tick counts depend on the axis length, so short subplot axes can
have too few ticks. Use `addAxes()` with `addTicksX()` and `addTicksY()` to
choose positions and labels explicitly, as above. Draw ticks before axis
labels so their spacing accounts for the tick text.

Plot continuous branches separately for functions with poles; see the
[discontinuous-function example](docs/plotting.md#discontinuous-functions).

`Figure` also accepts `wspace`, `hspace`, `padding`, `width_ratios`, and
`height_ratios`; `fig.subplots(x_range=..., y_range=...)` fills the whole grid
and returns `axes[row][col]`. Each subplot's SVG ids are prefixed on save so
markers, gradients, and LaTeX glyphs never collide.

### 4. Create a larger flow diagram

Nodes are identified by unique strings. Edges refer to those IDs and are
automatically clipped to the node boundaries.

<!-- render: core -->
```python
from svgflow import Flow

flow = Flow(height=210, width=660)

flow.addNode(
    "input", 85, 75,
    shape=("ellipse", 70, 40),
    label="Input",
    color="lightyellow",
)
flow.addNode(
    "validate", 315, 75,
    shape=("rectangle", 90, 150, 12),
    label="Validate",
    color="lightblue",
)
flow.addNode(
    "output", 565, 75,
    shape=("circle", 45),
    label="Output",
    color="lightgreen",
)

flow.addEdge("input", "validate", directed=True)
flow.addEdge("validate", "output", label="valid", directed=True)
flow.addSelfEdge(
    "validate",
    label="retry",
    curvature=90,
    color="gray",
)
flow.save("pipeline.svg")
```

![Rendered pipeline example](docs/figures/readme-pipeline.svg)

Supported node shapes are `("circle", radius)`,
`("rectangle", height, width[, corner_radius])`,
`("ellipse", horizontal_radius, vertical_radius)`, and parallelograms. Edges
meet each node's outline (including rounded corners).

Self-loops always bulge outward from the node: `addSelfEdge(node, theta1,
theta2, curvature)` leaves at angle `theta1` and returns at `theta2` (degrees,
clockwise from +x, so `90` is straight down); `curvature` sets the loop size.

#### Styling a whole diagram

`FlowStyle` holds the defaults for nodes and edges. Any argument you leave out
(or pass as `None`) comes from the style, so a diagram can be restyled in one
place while individual calls can still override anything:

<!-- render: core -->
```python
from svgflow import Flow, FlowStyle

style = FlowStyle(
    node_shape=("rectangle", 50, 120, 8),
    node_color="aliceblue", node_border="steelblue",
    edge_color="dimgray", arrow_style="stealth",
    text_size=14,
)
flow = Flow(100, 460, style=style)
flow.addNode("a", 85, 50, label="Load")
flow.addNode("b", 375, 50, label="Train", color="lightyellow")  # override
flow.addEdge("a", "b", directed=True, label="data")
flow.save("styled.svg")
```

![Rendered styled example](docs/figures/readme-styled.svg)

Fields: `node_shape`, `node_color`, `node_border`, `node_thickness`,
`text_size`, `text_color`, `text_style`, `edge_color`, `edge_thickness`,
`edge_text_size`, `edge_text_color`, `label_gap` (edge-label offset in em),
`arrow_style`, `arrow_size`, `stub` and `corner_radius` (elbow edges), and
`self_loop_size`. `style.copy(**changes)` derives variants.

### 5. Use gradients

Define each gradient once, retrieve its SVG paint value with `getGradient`, and
pass that value anywhere a fill color is accepted.

<!-- render: core -->
```python
from svgflow import Canvas

canvas = Canvas(200, 460)
canvas.defineLinearGradient(
    "sunset",
    x1=0,
    y1=0,
    x2=1,
    y2=1,
    stop_points=(0, 0.5, 1),
    stop_colors=("gold", "tomato", "purple"),
)
canvas.addRectangle(
    160, 420, 20, 20,
    color=canvas.getGradient("sunset"),
    border="none",
    corner_radius=24,
)
canvas.save("gradient.svg")
```

![Rendered gradient example](docs/figures/readme-gradient.svg)

`defineRadialGradient` works in the same way for radial fills.

### 6. Add LaTeX labels

LaTeX support requires `pdflatex` plus one conversion backend. The default
backend is Inkscape.

<!-- render: latex -->
```python
from svgflow import Canvas

canvas = Canvas(90, 220)
canvas.addLaTeX(
    r"e^{i\pi} + 1 = 0",
    x=110,
    y=45,
    scale=2.6,
    color="navy",
    backend="inkscape",  # or "dvisvgm" / "pdf2svg"
)
canvas.save("equation.svg")
```

![Rendered equation example](docs/figures/readme-equation.svg)

For integrals, matrices, piecewise functions, and an optimization diagram with
LaTeX node and edge labels, see the [math tutorial](docs/composition-and-export.md#add-math-labels).

#### An integral identity

<!-- render: latex -->
```python
from svgflow import Canvas

canvas = Canvas(110, 400)
canvas.addLaTeX(
    r"\int_{-\infty}^{\infty}e^{-a x^2}\,dx=\sqrt{\frac{\pi}{a}},\quad a>0",
    200, 55, scale=2.4, color="navy",
)
canvas.save("gaussian-integral.svg")
```

![Gaussian integral](docs/figures/readme-gaussian-integral.svg)

#### Equations in a flow diagram

<!-- render: latex -->
```python
from svgflow import Flow, FlowStyle

# LaTeX scales with text_size / 16. Size each box for its own equation.
style = FlowStyle(node_shape=("rectangle", 64, 180, 10),
                  node_color="aliceblue", node_border="steelblue",
                  text_size=32, edge_text_size=26)
f = Flow(230, 840, style=style)
f.addNode("loss", 150, 90, shape=("rectangle", 120, 260, 12), label=(
    r"\begin{aligned}\mathcal{L}(\theta)&=\frac{1}{n}\sum_{i=1}^{n}"
    r"(y_i-\theta^\top x_i)^2\\&\quad+\lambda\lVert\theta\rVert_2^2\end{aligned}"
), latex=True)
f.addNode("gradient", 450, 90, label=r"g_k=\nabla_\theta\mathcal{L}(\theta_k)",
          latex=True)
f.addNode("update", 720, 90, shape=("rectangle", 64, 200, 10),
          label=r"\theta_{k+1}=\theta_k-\eta_k g_k", latex=True, color="honeydew")
f.addEdge("loss", "gradient", directed=True)
f.addEdge("gradient", "update", directed=True)
f.addElbowEdge("update", "loss", from_port="S", to_port="S",
               waypoints=[(720, 205), (150, 205)],
               label=r"k\leftarrow k+1", latex=True)
f.save("optimization-flow.svg")
```

![Rendered optimization flow example](docs/figures/readme-optimization-flow.svg)

### 7. Reuse another SVG

Import an SVG once under a unique ID, then place as many transformed copies as
you need.

<!-- render: core -->
```python
from svgflow import Canvas

canvas = Canvas(130, 340)
canvas.importSvgFromFile("docs/figures/icon.svg", fig_id="icon")
canvas.addSubFig("icon", 85, 65, scale=1.2)
canvas.addSubFig("icon", 250, 65, scale=1.0, rot=30, flip=True)
canvas.save("composite.svg")
```

![Rendered composite example](docs/figures/readme-composite.svg)

The imported file must have an SVG `viewBox`. SvgFlow prefixes its internal IDs
to prevent gradient, mask, and clip-path collisions.

### 8. Export PNG or PDF

This continues the composition example above. Saving SVG is built in and requires
no external program. Raster and PDF exports
use Inkscape:

```python
canvas.save("figure.svg")
canvas.export("figure.png", export_type="png", dpi=300)
canvas.export("figure.pdf", export_type="pdf")
```

![Composition used for PNG and PDF export](docs/figures/readme-composite.svg)

Inkscape ignores the `@font-face` rules SvgFlow embeds for registered fonts, so
`export` runs Inkscape with a temporary fontconfig setup that exposes every
registered font file under its registered name. This helps keep exported text
consistent with the measured fonts; supplying all used face variants improves
consistency. The saved SVG still embeds file-backed fonts for supporting viewers.

## Configuring external programs

SvgFlow looks for optional commands on the system `PATH` by default. You can
instead supply explicit paths:

<!-- render: core -->
```python
from svgflow import Canvas, ExecutablePaths

tools = ExecutablePaths(
    inkscape=r"C:\Program Files\Inkscape\bin\inkscape.exe",
    pdflatex=r"C:\texlive\bin\windows\pdflatex.exe",
    dvisvgm=r"C:\texlive\bin\windows\dvisvgm.exe",
    pdf2svg=r"C:\tools\pdf2svg.exe",
)

canvas = Canvas(90, 260, executables=tools)
canvas.addText("Hello, SvgFlow!", 130, 45, size=22)
canvas.save("configured.svg")
```

![Configured canvas example](docs/figures/readme-configured.svg)

`Plot` and `Flow` accept the same `executables` keyword argument. The
lower-level `tex2svg` function accepts `executables=tools` as well.

## Developing locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Publishing a new release

PyPI releases are immutable: after publishing a version such as `0.1.0`, reuse
of that version is not allowed. For every release, choose a higher version and
update it in both `pyproject.toml` and `svgflow/__init__.py`.

1. Make and test your code and documentation changes.
2. Update both version strings. A typical bug fix changes `0.1.0` to `0.1.1`;
   a backward-compatible feature release usually changes it to `0.2.0`.
3. Remove artifacts from earlier builds so they cannot be uploaded by mistake.
4. Build fresh distributions and validate their metadata.

PowerShell:

```powershell
Remove-Item -Recurse -Force build, dist, svgflow.egg-info -ErrorAction SilentlyContinue
py -m pip install --upgrade build twine
py -m build
py -m twine check --strict .\dist\*
```

macOS/Linux:

```bash
rm -rf build dist svgflow.egg-info
python3 -m pip install --upgrade build twine
python3 -m build
python3 -m twine check --strict dist/*
```

The build should produce one `.tar.gz` source distribution and one `.whl`
wheel in `dist/`. Optionally test the release on TestPyPI first:

```bash
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ svgflow==NEW_VERSION
```

TestPyPI and PyPI use separate accounts and tokens. Once the package looks
correct, upload the same checked files to production:

```bash
python -m twine upload dist/*
```

When prompted for a token, paste the complete value including its `pypi-`
prefix. Then verify the public release in a clean environment:

```bash
python -m venv release-check
# Activate the environment, then:
python -m pip install svgflow==NEW_VERSION
python -c "import svgflow; print(svgflow.__version__)"
```

Finally, commit the version change and tag the exact release:

```bash
git add pyproject.toml svgflow/__init__.py README.md
git commit -m "Release NEW_VERSION"
git tag vNEW_VERSION
git push origin main --tags
```

For automated releases from GitHub Actions, prefer PyPI Trusted Publishing over
storing a long-lived API token in the repository.

## Contributing

Issues and pull requests are welcome. When reporting a problem, include your
Python version, operating system, and a minimal example that reproduces it.
