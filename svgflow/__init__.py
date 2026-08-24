"""Create SVG drawings, plots, and flow diagrams with Python."""

from .canvas import Canvas, Flow, Plot
from .external_figures import ExecutablePaths, import_svg_from_file, tex2svg

__all__ = [
    "Canvas",
    "ExecutablePaths",
    "Flow",
    "Plot",
    "import_svg_from_file",
    "tex2svg",
]

__version__ = "0.1.0"
