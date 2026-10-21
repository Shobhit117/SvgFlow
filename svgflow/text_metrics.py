"""Font registry and font-aware text measurement helpers.

Every font known to svgflow has two faces of the same coin:

* a CSS ``font-family`` string that is written into the SVG (what is *drawn*);
* a font file / PyMuPDF built-in used to compute glyph advances (what is *measured*).

Keeping both in one registry makes layout computations (legend sizes, word
wrapping, ``textLength``) use consistent font metrics. Built-in CSS fallback
fonts and viewer font substitution can still change the rendered appearance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

import pymupdf


DEFAULT_FONT_NAME = "helv"
DEFAULT_FONT_FAMILY = "Helvetica, Arial, sans-serif"
DEFAULT_FONT = "default"

# Variant keys used throughout the module.
REGULAR, BOLD, ITALIC, BOLD_ITALIC = "regular", "bold", "italic", "bold_italic"


@dataclass(frozen=True)
class FontSpec:
    """A registered font.

    ``faces`` maps a variant (regular/bold/italic/bold_italic) to either a path
    to a TTF/OTF file or the name of a PyMuPDF built-in font (e.g. ``"helv"``).
    ``embed`` controls whether file-based faces are embedded into saved SVGs
    via ``@font-face`` in viewers that support embedded fonts.
    """

    name: str
    family: str
    faces: dict[str, str] = field(default_factory=dict)
    embed: bool = True

    def face(self, bold: bool = False, italic: bool = False) -> str:
        """Return the best matching face, falling back towards regular."""
        wanted = BOLD_ITALIC if (bold and italic) else BOLD if bold else ITALIC if italic else REGULAR
        for key in (wanted, BOLD if bold else ITALIC if italic else REGULAR, REGULAR):
            if key in self.faces:
                return self.faces[key]
        raise KeyError(f"font {self.name!r} has no regular face")

    def css_family(self) -> str:
        """Family string for the SVG ``font-family`` attribute (quoted if needed)."""
        if self.embed and self.file_faces():
            # Embedded fonts are declared under their registry name; keep the
            # user-supplied family as a fallback chain.
            primary = f"'{self.name}'"
            return primary if self.family == self.name else f"{primary}, {self.family}"
        return self.family

    def file_faces(self) -> dict[str, str]:
        """Faces backed by real files (as opposed to PyMuPDF built-ins)."""
        return {k: v for k, v in self.faces.items() if os.path.isfile(v)}


_REGISTRY: dict[str, FontSpec] = {}


def register_font(
    name: str,
    regular: str,
    bold: str | None = None,
    italic: str | None = None,
    bold_italic: str | None = None,
    *,
    family: str | None = None,
    embed: bool = True,
) -> FontSpec:
    """Register a font so it can be used via ``addText(..., font=name)``.

    ``regular``/``bold``/``italic``/``bold_italic`` are paths to TTF/OTF files
    (or PyMuPDF built-in names). ``family`` is the CSS family written into the
    SVG; it defaults to ``name``. Re-registering a name replaces it.
    Registration is process-wide and returns the resulting ``FontSpec``.
    Faces are loaded immediately; invalid files or built-in names propagate
    the PyMuPDF loader's exception. Missing variants fall back towards regular.
    Only file-backed faces can be embedded; ``embed=False`` relies on viewer
    fonts for SVG display. Inkscape export exposes file faces separately.
    """
    faces = {REGULAR: str(regular)}
    for key, value in ((BOLD, bold), (ITALIC, italic), (BOLD_ITALIC, bold_italic)):
        if value is not None:
            faces[key] = str(value)
    for path in faces.values():
        # Validate early: this raises if the file/built-in can't be loaded.
        _load(path)
    spec = FontSpec(name=name, family=family or name, faces=faces, embed=embed)
    _REGISTRY[name] = spec
    return spec


def get_font(name: str | None) -> FontSpec:
    """Look up a registered font (``None`` means the default font)."""
    name = DEFAULT_FONT if name is None else name
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown font {name!r}; registered fonts: {sorted(_REGISTRY)}") from None


def available_fonts() -> list[str]:
    """Return registered font names in sorted order.

    Initially includes default, sans, serif and mono; registrations are shared
    across canvases in the current Python process, not saved between runs.
    """
    return sorted(_REGISTRY)


# Built-in PDF base-14 fonts: always available, never embedded.
for _name, _family, _faces in (
    (DEFAULT_FONT, DEFAULT_FONT_FAMILY, ("helv", "hebo", "heit", "hebi")),
    ("sans", DEFAULT_FONT_FAMILY, ("helv", "hebo", "heit", "hebi")),
    ("serif", "'Times New Roman', Times, serif", ("tiro", "tibo", "tiit", "tibi")),
    ("mono", "'Courier New', Courier, monospace", ("cour", "cobo", "coit", "cobi")),
):
    _REGISTRY[_name] = FontSpec(_name, _family, dict(zip((REGULAR, BOLD, ITALIC, BOLD_ITALIC), _faces)), embed=False)


@lru_cache(maxsize=None)
def _load(face: str) -> pymupdf.Font:
    """Return a cached PyMuPDF font from a file path or built-in name."""
    if os.path.isfile(face):
        return pymupdf.Font(fontfile=face)
    return pymupdf.Font(face)


def is_bold(weight: object) -> bool:
    """Interpret an SVG ``font-weight`` value."""
    if weight is None:
        return False
    if isinstance(weight, (int, float)):
        return weight >= 600
    w = str(weight).strip().lower()
    return w in {"bold", "bolder"} or (w.isdigit() and int(w) >= 600)


def is_italic(style: object) -> bool:
    """Interpret an SVG ``font-style`` value."""
    return style is not None and str(style).strip().lower() in {"italic", "oblique"}


def text_width(text: object, size: float, font: str = DEFAULT_FONT, bold: bool = False, italic: bool = False) -> float:
    """Return the advance width of *text* at *size* in SVG user units.

    ``font`` is a registered font name; for backwards compatibility a raw
    PyMuPDF built-in name (e.g. ``"helv"``) is also accepted.
    ``text`` is converted to str; this helper measures one line, not a block.
    ``bold``/``italic`` choose registered face variants. Negative sizes raise
    ``ValueError``. Invalid unregistered font names reach the font loader.
    The result is glyph advance width, not a tight ink bounding box.
    """
    if size < 0:
        raise ValueError("font size must be non-negative")
    face = _REGISTRY[font].face(bold, italic) if font in _REGISTRY else font
    return _load(face).text_length(str(text), fontsize=float(size))


def wrap_text(text: object, size: float, max_width: float, font: str = DEFAULT_FONT, bold: bool = False, italic: bool = False) -> list[str]:
    """Greedy word-wrap of *text* so each line fits within *max_width*.

    Explicit newlines are preserved. A single word wider than ``max_width`` is
    kept on its own line rather than being split.
    Returns a list of strings, including empty lines for empty paragraphs.
    Whitespace within paragraphs is normalized to single spaces; there is no
    hyphenation. ``size``/``max_width`` use the same SVG user units as addText.
    Font selection and invalid-size behavior follow :func:`text_width`.
    """
    lines: list[str] = []
    space = text_width(" ", size, font, bold, italic)
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current, current_w = words[0], text_width(words[0], size, font, bold, italic)
        for word in words[1:]:
            w = text_width(word, size, font, bold, italic)
            if current_w + space + w <= max_width:
                current += " " + word
                current_w += space + w
            else:
                lines.append(current)
                current, current_w = word, w
        lines.append(current)
    return lines
