# Troubleshooting and implementation limits

[Documentation home](README.md)

## Installation and imports

**`ModuleNotFoundError: svgflow`**: run `python -m pip install -e .` from the
repository root, using the interpreter that will run your drawing script.
Verify `sys.executable` and `svgflow.__file__`. A script named `svgflow.py`
can shadow the installed package; use a different filename.

**`ModuleNotFoundError: pymupdf` or `numpy`**: install the project and its
declared dependencies in that same environment. The import is `pymupdf`,
even though the distribution name is `PyMuPDF`. Both are required for the
current package import, including ordinary drawing.

## Empty, clipped, or misplaced drawings

**Width/height swapped**: constructors and `addRectangle` take height first.
Prefer keyword arguments when dimensions are easy to confuse.

**Wrong reference point**: a canvas rectangle starts at its top-left, while
a flow rectangle is centered at the node position. Circle/ellipse dimensions
are radii, and parallelogram dimensions are diagonals.

**Plot annotations in the wrong place**: inherited `addText`, `addLine`, and
shapes take canvas coordinates. Call `mapToCanvas` first. `putMarker` uses
data coordinates when `on_canvas=True` and raw coordinates when False.

**Data drawn over tick labels**: plots do not clip series to the data rectangle.
Choose appropriate ranges or filter/split your input data. NaN/infinity values
are not automatically removed. Zip-based series silently truncate mismatched
input lengths.

**Axes do not cross zero**: axes sit on the lower and left plot boundaries.
Draw additional mapped zero lines if desired.

**Lines across a discontinuity**: `addPlot()` joins adjacent values without
detecting poles or breaking on NaN/infinity. Draw each continuous visible
branch in a separate call. Clamping values creates false plateaus; see the
[tangent example](plotting.md#discontinuous-functions).

**Missing/downward bars**: bar width uses canvas units; y is an absolute top,
not a height. Tops below baselines create negative-height SVG rectangles.
See [signed bars](recipes.md) for a workaround.

**Too-small auto-layout warning**: reduce `PlotStyle` font sizes, enlarge
the canvas/cell, or supply explicit origin/margins. Percentage fallback keeps
the plot drawable but may leave insufficient room for text.

**Long or rotated tick labels overlap/clipped**: reserve `extra_margins` at
construction, e.g. `(0, 50, 0, 0)` for extra bottom room. Call ticks before
`addAxisLabels`. Automatic margins estimate endpoint labels, not all future
custom content, and are not recomputed after drawing.

**Unexpected series or legend order**: strokes follow input order; x values
are not sorted. Legends group entries by bar/plot/scatter type. Labels are
not deduplicated. `addLegend` requires a labeled series and a valid anchor,
or a custom position; `anchor=None` alone is insufficient.

**Grid cells overlap**: `subplot` creates plots rather than retrieving them.
Keep the returned reference. A spanning plot occupies every cell in its span.
Use `subplots()` only on an empty grid. Shared style does not guarantee exact
alignment when endpoint label widths differ; use explicit common margins.

## Flow geometry and styles

**`KeyError` on an edge**: create both nodes first; check the IDs. Use
`addSelfEdge` for a node connected to itself. Duplicate node IDs also fail.

**Unexpected curved edge bend**: curvature offsets the control point, not
the visible curve midpoint. Positive horizontal curvature bends up; positive
vertical curvature bends right. Self-loop signs are ignored; angles choose
which side of the node the loop occupies.

**An elbow edge crosses another node**: routing is geometric and does not
avoid obstacles. Move nodes, choose ports explicitly, or supply waypoints.
Waypoints are literal; they do not generate missing orthogonal bends.

**`label_segment` selects the wrong part**: indices refer to the simplified
returned route, after duplicate/collinear points are removed. Inspect that
route or use `"longest"`.

**Changing styles/nodes does not update the image**: drawing methods append
SVG immediately. Mutating a style affects future calls; mutating the node
registry does not move existing artwork. Rebuild from the Python source.
Flow edge `text_style` does not inherit the node style automatically.

**Some arrows are missing by default**: `addEdge` and `addSelfEdge` default
to no arrow; `addElbowEdge` defaults to a target arrow. Pass `directed`
explicitly for consistency.

## Fonts and SVG viewers

**Registered font unknown**: registry names differ from font-family names.
Register the font in the same Python process, then pass `font=registry_name`
or set the canvas default. `text_width` also accepts raw PyMuPDF built-in
names, but `addText` expects a registered name.

**Measured text differs from rendered text**: built-in metrics use PDF fonts
while SVG uses viewer fallback fonts. Register actual files and all variants
you use. Some viewers ignore embedded CSS or synthesize missing styles.
`fit_width=True` constrains advance width, not exact glyph shapes. The helper
does not provide general shaping, automatic script/font fallback or bidi layout.

**Fontconfig warning during export**: the base Inkscape font configuration
could not be found. Verify the configured executable and environment variables.
Export still proceeds with inherited fonts, which can cause substitution.

**Wrapped text still too wide**: an overlong word is never split. Shorten it,
insert an explicit line break, reduce size, or increase width. Text block
height is a layout estimate rather than a tight glyph bound.

## Imports, math, and output

**Imported SVG rejected**: the importer needs explicit `<svg>...</svg>`
structure and a whitespace-separated four-number `viewBox`. It does not infer
a viewBox from dimensions. Relative image/font resources are not bundled.

**Imported styling changes**: root attributes and arbitrary CSS references
are not fully normalized. Prefer self-contained SVG with internal definitions
and explicit element styling. ID prefixing handles common SVG references,
not every possible CSS/XML construct.

**A gradient repeat/reflect looks padded**: `spread_method` is validated but
not written into SVG in this version. Both gradient types use the default pad.
Gradient coordinates are relative to each object's bounding box.

**`FileNotFoundError` during math/export**: the needed command is missing from
PATH or its configured path is wrong. Supply `ExecutablePaths` with the full
executable path; do not add shell quotes. Basic SVG saving still works.

**`RuntimeError: pdflatex failed` or converter failure**: check that the math
contains no dollar delimiters, uses raw Python strings where needed, and
compiles with standalone/amsmath/amssymb. Each backend has its own PDF-input
requirements. Temporary logs are removed after the operation; reproduce the
expression in a standalone TeX file for detailed toolchain diagnostics.

**Exported “PDF” is actually PNG**: set `export_type="pdf"`; suffixes do not
select formats. `save("name.png")` still writes SVG. DPI applies only to PNG.

**Unexpected transparency**: canvases have no implicit background. Draw an
opaque rectangle first for a white page/image. The Markdown gallery does this.

## Boundaries of this version

SvgFlow is a compact SVG generator. It has no automatic data autoscaling,
logarithmic or date-axis abstraction, plot-area clipping, axis sharing,
interactive event system, general scene editing/undo, automatic flow layout,
obstacle-avoiding routing, arbitrary dash/marker customization, full SVG
sanitizer/parser, or LaTeX cache. Many presentation effects can be built with
mapped primitives; the [recipes](recipes.md) show examples. For features
outside the API, keep any preprocessing or custom SVG manipulation explicit.

When reporting a bug, include a minimal Python script, package/Python
versions, operating system, and the generated SVG. For optional integrations,
also include command locations, versions, and the conversion error text.
