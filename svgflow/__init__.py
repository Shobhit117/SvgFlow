"""Create SVG drawings, plots, and flow diagrams with Python."""

from .canvas import Canvas, Flow, Plot
from .external_figures import ExecutablePaths, import_svg_from_file, tex2svg
from .text_metrics import available_fonts, register_font, text_width, wrap_text

__all__ = [
    "Canvas",
    "ExecutablePaths",
    "Flow",
    "Plot",
    "available_fonts",
    "import_svg_from_file",
    "register_font",
    "tex2svg",
    "text_width",
    "wrap_text",
]

__version__ = "0.2.0"
