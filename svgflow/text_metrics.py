"""Font-aware text measurement helpers."""

from __future__ import annotations

from functools import lru_cache

import pymupdf


DEFAULT_FONT_NAME = "helv"
DEFAULT_FONT_FAMILY = "Helvetica, Arial, sans-serif"


@lru_cache(maxsize=None)
def _font(font_name: str) -> pymupdf.Font:
    """Return a cached PyMuPDF font instance."""
    return pymupdf.Font(font_name)


def text_width(text: object, size: float, font_name: str = DEFAULT_FONT_NAME) -> float:
    """Return the advance width of *text* at *size* in SVG user units.

    Glyph advances are fractions of the font's em size. Passing the SVG's
    numeric font size to PyMuPDF therefore returns the width in SVG user units.
    """
    if size < 0:
        raise ValueError("font size must be non-negative")
    return _font(font_name).text_length(str(text), fontsize=float(size))
