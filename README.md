# SvgFlow

SvgFlow is a lightweight Python library for creating SVG drawings, plots, and
flow diagrams. Drawings are assembled with Python and saved as editable SVG;
optional integrations add LaTeX labels and PNG/PDF export.

## Features

- Basic SVG shapes, text, paths, curves, arrows, and gradients
- `Plot` helpers for axes, ticks, lines, scatter plots, bars, and legends
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

```python
from svgflow import Flow

diagram = Flow(height=240, width=480)

diagram.addNode(
    "source", 100, 120,
    shape=("circle", 45),
    label="Source",
    color="lightblue",
)
diagram.addNode(
    "result", 380, 120,
    shape=("rectangle", 80, 120),
    label="Result",
    color="lightgreen",
)
diagram.addEdge("source", "result", label="transform", directed=True)
diagram.save("flow.svg")
```

The first `Canvas`, `Plot`, and `Flow` constructor argument is the height; the
second is the width. SVG coordinates start at the top-left corner.

## Tutorials

### 1. Build a drawing from shapes

`Canvas` is the base class. Drawing methods append elements in order, so later
elements appear on top of earlier ones.

```python
from svgflow import Canvas

canvas = Canvas(height=300, width=500)

canvas.addRectangle(
    height=120,
    width=220,
    x=140,
    y=90,
    color="aliceblue",
    border="steelblue",
    thickness=3,
    corner_radius=16,
)
canvas.addCircle(140, 150, radius=30, color="gold", border="orange")
canvas.addLine(
    170, 150, 330, 150,
    color="steelblue",
    thickness=3,
    directed=True,
    label="process",
)
canvas.addText("SvgFlow", 250, 60, size=24, weight="bold")
canvas.save("drawing.svg")
```

Useful drawing methods include `addText`, `addMultiLineText`, `addLine`,
`addCurvedLine`, `addRectangle`, `addCircle`, `addEllipse`, `addPolygon`, and
the line, quadratic, cubic, and fitted-curve path helpers.

### 2. Create a line and scatter plot

`Plot` maps data coordinates onto the SVG canvas. Set the visible data ranges
when creating it, then add axes and one or more data series.

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

Use `addTicksX` and `addTicksY` when you need complete control over tick values
and labels. `addBarPlot` adds vertical bars and can share a legend with line or
scatter series.

### 3. Create a larger flow diagram

Nodes are identified by unique strings. Edges refer to those IDs and are
automatically clipped to the node boundaries.

```python
from svgflow import Flow

flow = Flow(height=360, width=720)

flow.addNode(
    "input", 100, 180,
    shape=("ellipse", 70, 40),
    label="Input",
    color="lightyellow",
)
flow.addNode(
    "validate", 330, 180,
    shape=("rectangle", 90, 150, 12),
    label="Validate",
    color="lightblue",
)
flow.addNode(
    "output", 610, 180,
    shape=("circle", 55),
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

Supported node shapes are `("circle", radius)`,
`("rectangle", height, width[, corner_radius])`,
`("ellipse", horizontal_radius, vertical_radius)`, and parallelograms.

### 4. Use gradients

Define each gradient once, retrieve its SVG paint value with `getGradient`, and
pass that value anywhere a fill color is accepted.

```python
from svgflow import Canvas

canvas = Canvas(260, 520)
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
    160, 420, 50, 50,
    color=canvas.getGradient("sunset"),
    border="none",
    corner_radius=24,
)
canvas.save("gradient.svg")
```

`defineRadialGradient` works in the same way for radial fills.

### 5. Add LaTeX labels

LaTeX support requires `pdflatex` plus one conversion backend. The default
backend is Inkscape.

```python
from svgflow import Canvas

canvas = Canvas(200, 500)
canvas.addLaTeX(
    r"e^{i\pi} + 1 = 0",
    x=250,
    y=100,
    scale=2,
    color="navy",
    backend="inkscape",  # or "dvisvgm" / "pdf2svg"
)
canvas.save("equation.svg")
```

### 6. Reuse another SVG

Import an SVG once under a unique ID, then place as many transformed copies as
you need.

```python
from svgflow import Canvas

canvas = Canvas(400, 700)
canvas.importSvgFromFile("icon.svg", fig_id="icon")
canvas.addSubFig("icon", 180, 200, scale=0.8)
canvas.addSubFig("icon", 500, 200, scale=0.5, rot=30, flip=True)
canvas.save("composite.svg")
```

The imported file must have an SVG `viewBox`. SvgFlow prefixes its internal IDs
to prevent gradient, mask, and clip-path collisions.

### 7. Export PNG or PDF

Saving SVG is built in and requires no external program. Raster and PDF exports
use Inkscape:

```python
canvas.save("figure.svg")
canvas.export("figure.png", export_type="png", dpi=300)
canvas.export("figure.pdf", export_type="pdf")
```

## Configuring external programs

SvgFlow looks for optional commands on the system `PATH` by default. You can
instead supply explicit paths:

```python
from svgflow import Canvas, ExecutablePaths

tools = ExecutablePaths(
    inkscape=r"C:\Program Files\Inkscape\bin\inkscape.exe",
    pdflatex=r"C:\texlive\bin\windows\pdflatex.exe",
    dvisvgm=r"C:\texlive\bin\windows\dvisvgm.exe",
    pdf2svg=r"C:\tools\pdf2svg.exe",
)

canvas = Canvas(400, 600, executables=tools)
canvas.addText("Hello, SvgFlow!", 300, 200)
canvas.save("drawing.svg")
```

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
