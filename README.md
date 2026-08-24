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

## Building the package

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

The source distribution and wheel are written to `dist/`.

## Publishing

Test the release on TestPyPI before uploading it to the production index:

```bash
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple svgflow
```

When the test package is correct, publish it to PyPI:

```bash
python -m twine upload dist/*
```

Use a PyPI API token when Twine asks for credentials: enter `__token__` as the
username and the complete token (including its `pypi-` prefix) as the password.
Every release must use a version that has not already been uploaded; update the
version in `pyproject.toml` and `svgflow/__init__.py` before rebuilding.

## Contributing

Issues and pull requests are welcome. When reporting a problem, include your
Python version, operating system, and a minimal example that reproduces it.
