# Author: Shobhit Bhatnagar
# email: shb.bhatnagar.96@gmail.com
# Requires: numpy and inkscape

"""Small SVG generation library for drawings, plots, and flow diagrams."""

from __future__ import annotations

import base64
import os
import re
import tempfile
import warnings
from xml.sax.saxutils import escape as xml_escape
import numpy as np
from .external_figures import ExecutablePaths, import_svg_from_file, tex2svg, uniquify_svg_ids
from .inkscape_fonts import inkscape_font_env
from subprocess import run, CalledProcessError
from typing import Any, Iterable, Literal, Sequence, TypeAlias
from .text_metrics import DEFAULT_FONT, BOLD, BOLD_ITALIC, ITALIC, get_font, is_bold, is_italic, register_font, text_width, wrap_text

Number: TypeAlias = int | float | np.number
Point: TypeAlias = tuple[Number, Number]
Color: TypeAlias = str
TextBaseline: TypeAlias = Literal["hanging", "middle", "text-top", "auto"]
PositionBaseline: TypeAlias = Literal["hanging", "middle", "text-top"]
TextAnchor: TypeAlias = Literal["start", "middle", "end"]
SvgBackend: TypeAlias = Literal["inkscape", "dvisvgm", "pdf2svg"]
MarkerType: TypeAlias = Literal["circle", "cross", "square"]
LegendAnchor: TypeAlias = Literal["NE", "N", "NW", "W", "E", "SW", "S", "SE"]
ExportType: TypeAlias = Literal["png", "pdf"]
GradientSpread: TypeAlias = Literal["pad", "reflect", "repeat"]
NodeShape: TypeAlias = tuple[Any, ...]
Port: TypeAlias = Literal["N", "S", "E", "W"]
ArrowStyle: TypeAlias = Literal["curved", "open", "triangle", "stealth"]
Directed: TypeAlias = bool | Literal["start", "end", "both"]

# Unit arrowheads: tip at the origin pointing along +x, length 10.
# Maps style -> (path data, filled?). Stroked heads take the line's thickness.
ARROW_SHAPES: dict[str, tuple[str, bool]] = {
    'curved': ('M-10 -5 Q-5 -0.5 0 0 Q-5 0.5 -10 5', False),
    'open': ('M-10 -5 L0 0 L-10 5', False),
    'triangle': ('M0 0 L-10 -4 L-10 4 Z', True),
    'stealth': ('M0 0 L-10 -4.5 L-7 0 L-10 4.5 Z', True),
}

NAMED_COLORS = {'none', 'aliceblue', 'antiquewhite', 'aqua', 'aquamarine', 'azure', 'beige', 'bisque', 'black', 'blanchedalmond', 'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue', 'chartreuse', 'chocolate', 'coral', 'cornflowerblue', 'cornsilk', 'crimson', 'cyan', 'darkblue', 'darkcyan', 'darkgoldenrod', 'darkgray', 'darkgreen', 'darkgrey', 'darkkhaki', 'darkmagenta', 'darkolivegreen', 'darkorange', 'darkorchid', 'darkred', 'darksalmon', 'darkseagreen', 'darkslateblue', 'darkslategray', 'darkslategrey', 'darkturquoise', 'darkviolet', 'deeppink', 'deepskyblue', 'dimgray', 'dimgrey', 'dodgerblue', 'firebrick', 'floralwhite', 'forestgreen', 'fuchsia', 'gainsboro', 'ghostwhite', 'gold', 'goldenrod', 'gray', 'green', 'greenyellow', 'grey', 'honeydew', 'hotpink', 'indianred', 'indigo', 'ivory', 'khaki', 'lavender', 'lavenderblush', 'lawngreen', 'lemonchiffon', 'lightblue', 'lightcoral', 'lightcyan', 'lightgoldenrodyellow', 'lightgray', 'lightgreen', 'lightgrey', 'lightpink', 'lightsalmon', 'lightseagreen', 'lightskyblue', 'lightslategray', 'lightslategrey', 'lightsteelblue', 'lightyellow', 'lime', 'limegreen', 'linen', 'magenta', 'maroon', 'mediumaquamarine', 'mediumblue', 'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslateblue', 'mediumspringgreen', 'mediumturquoise', 'mediumvioletred', 'midnightblue', 'mintcream', 'mistyrose', 'moccasin', 'navajowhite', 'navy', 'oldlace', 'olive', 'olivedrab', 'orange', 'orangered', 'orchid', 'palegoldenrod', 'palegreen', 'paleturquoise', 'palevioletred', 'papayawhip', 'peachpuff', 'peru', 'pink', 'plum', 'powderblue', 'purple', 'red', 'rosybrown', 'royalblue', 'saddlebrown', 'salmon', 'sandybrown', 'seagreen', 'seashell', 'sienna', 'silver', 'skyblue', 'slateblue', 'slategray', 'slategrey', 'snow', 'springgreen', 'steelblue', 'tan', 'teal', 'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white', 'whitesmoke', 'yellow', 'yellowgreen'}

class Canvas:
    """Mutable SVG canvas.

    Coordinates are expressed in SVG user units with the origin in the top-left
    corner. Drawing methods append SVG snippets to the canvas; call :meth:`save`
    to write the SVG file or :meth:`export` to rasterize/convert with Inkscape.
    """

    def __init__(self, height: Number, width: Number, *, executables: ExecutablePaths | None = None) -> None:
        """Create a blank canvas with the given pixel/user-unit dimensions."""
        # self.arrowLen = 10 # Default arrow size
        self.gap = 7.5
        self.height = height
        self.width = width
        self.executables = executables or ExecutablePaths()
        self.contents = []
        self.defs = []
        self.is_arrow_def_included = False
        self._arrow_defs: set[str] = set()
        # Default arrowhead shape for every directed stroke on this canvas:
        # "curved" (classic), "open" (straight chevron), "triangle" or "stealth".
        self.arrow_style: ArrowStyle = "curved"
        self.default_font = DEFAULT_FONT
        self.used_fonts = set()
        self.curr_latex_eq_num = 0
        self.gradients = set()
        self.sub_figs = set()
        self.sub_fig_dims = dict()
        self.capture_rgb = re.compile(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$', re.IGNORECASE)
        self.capture_url = re.compile(r'^url\(\s*#([^\s]+)\s*\)$', re.IGNORECASE)

    def _isValidColor(self, color: Color) -> bool:
        # Check if the color is one of the named colors:
        if color in NAMED_COLORS:
            return True
        # Check if color is specified in rgb format:
        match = self.capture_rgb.fullmatch(color)
        if match:
            r_str, g_str, b_str = match.groups()
            try:
                r = int(r_str)
                g = int(g_str)
                b = int(b_str)
                return (0 <= r <= 255) and (0 <= g <= 255) and (0 <= b <= 255)
            except ValueError:
                return False
        # Check if color is a url to a gradient:
        match = self.capture_url.fullmatch(color)
        if match:
            grad_id = match.group(1)
            if grad_id.startswith('grad_'):
                if grad_id[5:] in self.gradients:
                    return True
                else:
                    return False
            else:
                return False # invalid gradient reference
        return False

    def registerFont(self, name: str, regular: str | os.PathLike[str], bold: str | os.PathLike[str] | None = None, italic: str | os.PathLike[str] | None = None, bold_italic: str | os.PathLike[str] | None = None, *, family: str | None = None, embed: bool = True, make_default: bool = False) -> None:
        """Register a TTF/OTF font for use with ``addText(..., font=name)``.

        Fonts are measured with the actual font file, and (if ``embed``) the
        font data is embedded into the saved SVG so it renders identically
        everywhere. ``make_default`` makes it this canvas's default font.
        """
        register_font(name, regular, bold, italic, bold_italic, family=family, embed=embed)
        if make_default:
            self.default_font = name

    def _textLines(self, text: Any, size: Number, font: str, bold: bool, italic: bool, max_width: Number | None) -> list[str]:
        if isinstance(text, (list, tuple)):
            text = '\n'.join(str(t) for t in text)
        text = str(text)
        if max_width is not None:
            return wrap_text(text, size, max_width, font, bold, italic)
        return text.split('\n')

    def addText(self, text: Any, x: Number, y: Number, color: Color = "black", rotation: Number = 0, baseline: TextBaseline = "middle", anchor: TextAnchor = "middle", size: Number = 16, style: str | None = None, weight: str | Number | None = None, *, font: str | None = None, line_height: Number = 1.2, max_width: Number | None = None, fit_width: bool = False, valign: Literal["top", "center", "bottom"] | None = None) -> tuple[float, float]:
        """Add (possibly multi-line) text at ``(x, y)``.

        ``text`` may contain ``\\n`` or be a list of lines. ``max_width`` enables
        automatic word wrapping. The block is aligned as a whole according to
        ``baseline``: ``"middle"`` centres it on ``y``, ``"hanging"`` grows
        downward from ``y`` and ``"text-top"``/``"auto"`` grow upward so the
        last line sits at ``y``. Pass ``valign`` (top/center/bottom) to place
        the block independently of the per-line ``baseline``. ``font`` is a
        registered font name (see
        :meth:`registerFont`); ``fit_width`` forces each rendered line to the
        measured width via ``textLength``. Text is XML-escaped automatically.

        Returns the measured ``(width, height)`` of the text block.
        """
        # dominant-baseline: hanging, middle, text-top, auto
        # text-anchor: start, middle, end
        font = self.default_font if font is None else font
        spec = get_font(font)
        bold, italic = is_bold(weight), is_italic(style)
        self.used_fonts.add(font)

        lines = self._textLines(text, size, font, bold, italic, max_width)
        widths = [text_width(line, size, font, bold, italic) for line in lines]
        n = len(lines)

        text_options = [f'font-family="{xml_escape(spec.css_family(), {chr(34): "&quot;"})}"', f'font-size="{size}"']
        if style is not None:
            text_options.append(f'font-style="{style}"')
        if weight is not None:
            text_options.append(f'font-weight="{weight}"')
        text_options = ' '.join(text_options)

        def length_options(i: int) -> str:
            return f' textLength="{widths[i]:.4f}" lengthAdjust="spacingAndGlyphs"' if fit_width else ''

        if n == 1:
            body = f'<text{length_options(0)}'
            inner = xml_escape(lines[0])
        else:
            if valign is None:
                valign = {'middle': 'center', 'hanging': 'top'}.get(baseline, 'bottom')
            if valign == 'center':
                first_dy = -(n - 1) / 2 * line_height
            elif valign == 'bottom':
                first_dy = -(n - 1) * line_height
            else:  # top
                first_dy = 0
            spans = [f'<tspan x="0" dy="{first_dy:.4f}em"{length_options(0)}>{xml_escape(lines[0])}</tspan>']
            spans += [f'<tspan x="0" dy="{line_height}em"{length_options(i)}>{xml_escape(lines[i])}</tspan>' for i in range(1, n)]
            body = '<text'
            inner = ''.join(spans)
        self.contents.append(f'{body} fill="{color}" transform="translate({x:.4f} {y:.4f}) rotate({rotation:.4f})" dominant-baseline="{baseline}" text-anchor="{anchor}" {text_options}>{inner}</text>')
        return (max(widths, default=0.0), n * line_height * size)

    def addMultiLineText(self, lines: Sequence[Any], x: Number, y: Number, color: Color = "black", rotation: Number = 0, baseline: TextBaseline = "middle", anchor: TextAnchor = "middle", size: Number = 16, style: str | None = None, weight: str | Number | None = None, **kwargs: Any) -> tuple[float, float]:
        """Deprecated: :meth:`addText` now accepts lists and ``\\n`` directly."""
        if not lines:
            return (0.0, 0.0)
        return self.addText(list(lines), x, y, color, rotation, baseline, anchor, size, style, weight, **kwargs)

    def _fontFaceCss(self, fonts: Iterable[str] | None = None) -> str:
        # Builds @font-face rules for every used, embeddable, file-backed font.
        formats = {'.ttf': 'truetype', '.otf': 'opentype', '.woff': 'woff', '.woff2': 'woff2'}
        variants = {BOLD: ('bold', 'normal'), ITALIC: ('normal', 'italic'), BOLD_ITALIC: ('bold', 'italic')}
        rules = []
        for name in sorted(self.used_fonts if fonts is None else fonts):
            spec = get_font(name)
            if not spec.embed:
                continue
            for variant, path in spec.file_faces().items():
                weight, style = variants.get(variant, ('normal', 'normal'))
                fmt = formats.get(os.path.splitext(path)[1].lower(), 'truetype')
                with open(path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('ascii')
                rules.append(f"@font-face {{ font-family: '{name}'; font-weight: {weight}; font-style: {style}; src: url(data:font/{fmt};base64,{data}) format('{fmt}'); }}")
        return '\n'.join(rules)

    # ------------------------------------------------------------------ #
    # Strokes and arrowheads
    # ------------------------------------------------------------------ #
    #
    # Every stroked primitive (lines, curves, paths, arcs, edges) goes through
    # the same pipeline:
    #   1. `_arrowEnds` decodes `directed` into (start, end) flags;
    #   2. `_arrowMetrics` sizes the head from the line thickness and style;
    #   3. the geometry is trimmed so the stroke ends *inside* the head (a butt
    #      line end would otherwise poke out past a pointed tip);
    #   4. `_emitStroke` writes the stroke and heads, grouping them when
    #      translucent so overlaps are not darkened twice.

    def _arrowEnds(self, directed: Directed) -> tuple[bool, bool]:
        # Decodes the `directed` argument into (arrow at start, arrow at end).
        if directed is True or directed == 'end':
            return (False, True)
        if directed is False or directed is None:
            return (False, False)
        if directed == 'start':
            return (True, False)
        if directed == 'both':
            return (True, True)
        raise ValueError(f"invalid directed value {directed!r}: use True/False, 'start', 'end' or 'both'")

    def _arrowMetrics(self, thickness: Number, arrow_size: Number, arrow_style: ArrowStyle | None) -> tuple[str, float, float, float]:
        # Returns (style, scale, tip_back, line_back): the head is the unit shape
        # scaled by `scale`; its tip is moved back by `tip_back` so stroked heads
        # don't overshoot the target point; the stroke is shortened by `line_back`.
        style = self.arrow_style if arrow_style is None else arrow_style
        if style not in ARROW_SHAPES:
            raise ValueError(f"invalid arrow style {style!r}: supported styles are {', '.join(ARROW_SHAPES)}")
        scale = float(arrow_size) * max(1.0, float(thickness) / 2)
        if ARROW_SHAPES[style][1]:  # filled: tip exact, stroke ends mid-head
            return style, scale, 0.0, 5.0 * scale
        return style, scale, float(thickness) / 2, float(thickness)

    def _arrowheadMarkup(self, x: Number, y: Number, theta: Number, thickness: Number, color: Color, opacity: Number, style: str, scale: float, tip_back: float) -> str:
        def_id = 'arrow' if style == 'curved' else f'arrow_{style}'
        if def_id not in self._arrow_defs:
            self.defs.append(f'<path id="{def_id}" d="{ARROW_SHAPES[style][0]}"/>')
            self._arrow_defs.add(def_id)
            self.is_arrow_def_included = True
        rad = np.deg2rad(theta)
        x, y = x - tip_back * np.cos(rad), y - tip_back * np.sin(rad)
        if ARROW_SHAPES[style][1]:
            paint = f'fill="{color}" stroke="none"'
        else:
            paint = f'stroke="{color}" stroke-width="{thickness / scale:.4f}" stroke-linejoin="round" stroke-linecap="round" fill="none"'
        return f'<use xlink:href="#{def_id}" transform="translate({x:.4f} {y:.4f}) rotate({theta:.4f}) scale({scale:.4f} {scale:.4f})" {paint} opacity="{opacity}"/>'

    def addArrowhead(self, x: Number, y: Number, angle: Number, color: Color = 'black', thickness: Number = 1, opacity: Number = 1, arrow_size: Number = 1, arrow_style: ArrowStyle | None = None) -> None:
        """Draw a standalone arrowhead with its tip at ``(x, y)``.

        ``angle`` is the direction the arrow points, in degrees clockwise from
        the +x axis (SVG convention). The head is sized for a line of the given
        ``thickness`` (see :attr:`arrow_style` for the available shapes).
        """
        style, scale, tip_back, _ = self._arrowMetrics(thickness, arrow_size, arrow_style)
        self.contents.append(self._arrowheadMarkup(x, y, angle, thickness, color, opacity, style, scale, tip_back))

    def _addArrow(self, x: Number, y: Number, theta: Number, thickness: Number = 2, color: Color = 'black', opacity: Number = 1, size: Number = 1) -> None:
        # Kept for backwards compatibility; use addArrowhead.
        self.addArrowhead(x, y, theta, color, thickness, opacity, size)

    def _emitStroke(self, shape: str, color: Color, thickness: Number, opacity: Number, dashed: bool = False, fill: Color = 'none', heads: Sequence[tuple[Number, Number, Number]] = (), arrow: tuple[str, float, float] | None = None) -> None:
        # `shape` is an unterminated SVG element, e.g. '<path d="..."'.
        grouped = bool(heads) and opacity < 1
        op = 1 if grouped else opacity
        dash = ' stroke-dasharray="4"' if dashed else ''
        elements = [f'{shape} stroke="{color}" stroke-width="{thickness}" fill="{fill}" opacity="{op}"{dash}/>']
        if heads:
            style, scale, tip_back = arrow
            elements += [self._arrowheadMarkup(x, y, theta, thickness, color, op, style, scale, tip_back) for (x, y, theta) in heads]
        if grouped:
            self.contents.append(f'<g opacity="{opacity}">' + ''.join(elements) + '</g>')
        else:
            self.contents.extend(elements)

    @staticmethod
    def _deCasteljau(ctrl: Sequence[Point], t: float) -> tuple[list[Point], list[Point]]:
        # Splits a Bezier curve of any degree at parameter t.
        pts = [np.asarray(p, dtype=float) for p in ctrl]
        left, right = [pts[0]], [pts[-1]]
        while len(pts) > 1:
            pts = [(1 - t) * a + t * b for a, b in zip(pts[:-1], pts[1:])]
            left.append(pts[0])
            right.append(pts[-1])
        return [tuple(p) for p in left], [tuple(p) for p in reversed(right)]

    @classmethod
    def _trimBezier(cls, ctrl: Sequence[Point], distance: float, at_end: bool = True) -> list[Point]:
        # Shortens a Bezier segment (degree >= 1) by `distance` of arc length at
        # one end, never removing more than 45% of the segment.
        if distance <= 0:
            return list(ctrl)
        ts = np.linspace(0, 1, 65)
        samples = np.array([cls._deCasteljau(ctrl, t)[0][-1] for t in ts])
        cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(samples, axis=0).T))])
        total = cum[-1]
        if total == 0:
            return list(ctrl)
        distance = min(distance, 0.45 * total)
        if at_end:
            t = float(np.interp(total - distance, cum, ts))
            return cls._deCasteljau(ctrl, t)[0]
        t = float(np.interp(distance, cum, ts))
        return cls._deCasteljau(ctrl, t)[1]

    def _tangentAngle(self, ctrl: Sequence[Point], at_end: bool = True) -> Number:
        # Direction (degrees) in which a Bezier segment leaves its end (or start)
        # point, skipping control points that coincide with it.
        pts = list(ctrl) if at_end else list(ctrl)[::-1]
        tip = pts[-1]
        for p in reversed(pts[:-1]):
            if np.hypot(tip[0] - p[0], tip[1] - p[1]) > 1e-9:
                return self._getRot(p[0], p[1], tip[0], tip[1])
        return 0

    def _strokeSegments(self, segments: list[list[Point]], color: Color, thickness: Number, closed: bool, fill: Color, opacity: Number, directed: Directed, dashed: bool, arrow_size: Number, arrow_style: ArrowStyle | None) -> None:
        # Draws a chain of Bezier segments (2 points = line, 3 = quadratic,
        # 4 = cubic) with optional arrowheads at either end.
        start, end = self._arrowEnds(directed)
        heads: list[tuple[Number, Number, Number]] = []
        arrow = None
        if start or end:
            style, scale, tip_back, line_back = self._arrowMetrics(thickness, arrow_size, arrow_style)
            arrow = (style, scale, tip_back)
            segments = [list(s) for s in segments]
            if end:
                heads.append((*segments[-1][-1], self._tangentAngle(segments[-1], at_end=True)))
                if not closed:
                    segments[-1] = self._trimBezier(segments[-1], line_back, at_end=True)
            if start:
                heads.append((*segments[0][0], self._tangentAngle(segments[0], at_end=False)))
                if not closed:
                    segments[0] = self._trimBezier(segments[0], line_back, at_end=False)
        commands = {2: 'L', 3: 'Q', 4: 'C'}
        d = [f'M{segments[0][0][0]:.4f} {segments[0][0][1]:.4f}']
        for seg in segments:
            if len(seg) not in commands:
                raise ValueError("path segments must have 2, 3 or 4 points")
            d.append(commands[len(seg)] + ' '.join(f'{float(px):.4f} {float(py):.4f}' for (px, py) in seg[1:]))
        if closed:
            d.append('Z')
        self._emitStroke(f'<path d="{" ".join(d)}"', color, thickness, opacity, dashed, fill, heads, arrow)

    def addLine(self, x1: Number, y1: Number, x2: Number, y2: Number, color: Color = "black", thickness: Number = 1, dashed: bool = False, directed: Directed = False, opacity: Number = 1, label: Any | None = None, text_color: Color = "black", text_size: Number = 16, text_style: str | None = None, arrow_size: Number = 1, latex: bool = False, *, arrow_style: ArrowStyle | None = None, label_gap: Number = 0.4) -> Number:
        """Draw a straight line and optionally add arrowheads and a label.

        ``directed`` is ``True``/``"end"`` (arrow at ``(x2, y2)``), ``"start"``,
        ``"both"`` or ``False``. ``arrow_size`` scales the head relative to its
        default size for this ``thickness``; ``arrow_style`` overrides the
        canvas-wide :attr:`arrow_style`. ``label_gap`` is the label offset from the
        line in units of ``text_size``. Returns the line angle in degrees.
        """
        theta = self._getRot(x1, y1, x2, y2)
        start, end = self._arrowEnds(directed)
        (a1, b1), (a2, b2) = (x1, y1), (x2, y2)
        heads: list[tuple[Number, Number, Number]] = []
        arrow = None
        if start or end:
            style, scale, tip_back, line_back = self._arrowMetrics(thickness, arrow_size, arrow_style)
            arrow = (style, scale, tip_back)
            if end:
                heads.append((x2, y2, theta))
                (a2, b2) = self._trimBezier([(a1, b1), (a2, b2)], line_back, at_end=True)[-1]
            if start:
                heads.append((x1, y1, theta + 180))
                (a1, b1) = self._trimBezier([(a1, b1), (a2, b2)], line_back, at_end=False)[0]
        self._emitStroke(f'<line x1="{a1:.4f}" y1="{b1:.4f}" x2="{a2:.4f}" y2="{b2:.4f}"', color, thickness, opacity, dashed, 'none', heads, arrow)

        if label is not None:
            # Keep the text upright-ish and offset it along *its own* "up"
            # direction; the block grows that way, away from the line.
            rot = theta if -90 < theta < 90 else theta - 180
            ux, uy = np.sin(np.deg2rad(rot)), -np.cos(np.deg2rad(rot))
            gap = 0 if latex else text_size * label_gap
            (x3, y3) = ((x1 + x2) / 2 + gap * ux, (y1 + y2) / 2 + gap * uy)
            if latex:
                self.addLaTeX(label, x3, y3, scale=(text_size)/16, rot=rot, baseline="text-top", anchor="middle", color=text_color)
            else:
                self.addText(label, x3, y3, text_color, rot, "text-top", "middle", text_size, text_style)

        return theta

    def addCurvedLine(self, x1: Number, y1: Number, x2: Number, y2: Number, curvature: Number, color: Color = "black", thickness: Number = 1, dashed: bool = False, directed: Directed = False, opacity: Number = 1, label: Any | None = None, text_color: Color = "black", text_size: Number = 16, text_style: str | None = None, arrow_size: Number = 1, latex: bool = False, *, arrow_style: ArrowStyle | None = None, label_gap: Number = 0.4) -> Point:
        """Draw a quadratic Bezier curve controlled by a signed curvature value."""
        (cx, cy) = self._getControlPoint(x1, y1, x2, y2, curvature)
        if curvature == 0:
            self.addLine(x1, y1, x2, y2, color, thickness, dashed, directed, opacity, label, text_color, text_size, text_style, arrow_size, latex, arrow_style=arrow_style, label_gap=label_gap)
        else:
            self._strokeSegments([[(x1, y1), (cx, cy), (x2, y2)]], color, thickness, False, 'none', opacity, directed, dashed, arrow_size, arrow_style)
            if label is not None:
                self._curvedLabel(x1, y1, x2, y2, curvature, label, text_color, text_size, text_style, latex, label_gap)
        return (cx, cy)

    def _curvedLabel(self, x1: Number, y1: Number, x2: Number, y2: Number, curvature: Number, label: Any, text_color: Color, text_size: Number, text_style: str | None, latex: bool, label_gap: Number) -> None:
        # Places a label just outside the apex of a quadratic curve whose
        # control point is offset `curvature` from the chord midpoint.
        nx, ny = self._perpUnit(x1, y1, x2, y2)
        side = 1 if curvature > 0 else -1
        ox, oy = side * nx, side * ny                     # outward from the apex
        alpha = self._getRot(x1, y1, x2, y2)
        rot = alpha if -90 < alpha < 90 else alpha - 180
        ux, uy = np.sin(np.deg2rad(rot)), -np.cos(np.deg2rad(rot))  # text "up"
        # Grow the (possibly multi-line) block away from the curve: upward in
        # the text's frame if "outward" is the text's up, otherwise downward.
        baseline = "text-top" if ox * ux + oy * uy > 0 else "hanging"
        extra = 0 if latex else text_size * label_gap
        x3 = (x1 + x2) / 2 + nx * curvature / 2 + ox * extra
        y3 = (y1 + y2) / 2 + ny * curvature / 2 + oy * extra
        if latex:
            self.addLaTeX(label, x3, y3, scale=(text_size)/16, rot=rot, baseline=baseline, anchor="middle", color=text_color)
        else:
            self.addText(label, x3, y3, text_color, rot, baseline, "middle", text_size, text_style)

    @staticmethod
    def _perpUnit(x1: Number, y1: Number, x2: Number, y2: Number) -> Point:
        # Unit normal used for curvature offsets (positive curvature bends
        # towards this side of the chord from (x1, y1) to (x2, y2)).
        if x2 - x1 != 0:
            m = (y2 - y1) / (x2 - x1)
            return (m / np.sqrt(1 + m**2), -1 / np.sqrt(1 + m**2))
        return (1.0, 0.0)

    def _getControlPoint(self, x1: Number, y1: Number, x2: Number, y2: Number, c: Number) -> Point:
        nx, ny = self._perpUnit(x1, y1, x2, y2)
        return ((x1 + x2) / 2 + c * nx, (y1 + y2) / 2 + c * ny)

    def _getRot(self, x1: Number, y1: Number, x2: Number, y2: Number) -> Number:
        if x2 - x1 == 0:
            theta = 90 * np.sign(y2 - y1)
        elif x2 - x1 > 0:
            theta = np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi
        else:
            theta = 180 + np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi
        return theta # -90 <= theta <= 270

    def addRectangle(self, height: Number, width: Number, x: Number, y: Number, color: Color = "none", border: Color = "black", thickness: Number = 1, rotation: Number = 0, opacity: Number = 1, corner_radius: Number = 0) -> None:
        """Add a rectangle whose top-left corner is transformed to ``(x, y)``."""
        self.contents.append(f'<rect width="{width}" height="{height}" fill="{color}" stroke="{border}" stroke-width="{thickness}" transform="translate({x:.4f} {y:.4f}) rotate({rotation:.4f})" opacity="{opacity}" rx="{corner_radius}"/>')

    def addCircle(self, x: Number, y: Number, radius: Number, color: Color = "none", border: Color = "black", thickness: Number = 1, opacity: Number = 1) -> None:
        """Add a circle centered at ``(x, y)``."""
        self.contents.append(f'<circle cx="{x:.4f}" cy="{y:.4f}" r="{radius:.4f}" fill="{color}" stroke="{border}" stroke-width="{thickness}" opacity="{opacity}"/>')

    def addEllipse(self, x: Number, y: Number, a: Number, b: Number, color: Color = "none", border: Color = "black", thickness: Number = 1, rotation: Number = 0, opacity: Number = 1) -> None:
        """Add an ellipse centered at ``(x, y)`` with radii ``a`` and ``b``."""
        self.contents.append(f'<ellipse transform="translate({x:.4f} {y:.4f}) rotate({rotation:.4f})" rx="{a:.4f}" ry="{b:.4f}" fill="{color}" stroke="{border}" stroke-width="{thickness}" opacity="{opacity}"/>')

    def addPolygon(self, points: Sequence[Point], color: Color = "none", border: Color = "black", thickness: Number = 1, opacity: Number = 1) -> None:
        """Add a polygon through the supplied points."""
        p_str = [f'{float(p[0]):.4f},{float(p[1]):.4f}' for p in points]
        p_str = ' '.join(p_str)
        self.contents.append(f'<polygon points="{p_str}" fill="{color}" stroke="{border}" stroke-width="{thickness}" opacity="{opacity}"/>')
    
    def addLinePath(self, points: Sequence[Point], color: Color = "black", thickness: Number = 1, closed: bool = False, fill: Color = "none", opacity: Number = 1, directed: Directed = False, dashed: bool = False, arrow_size: Number = 1, *, arrow_style: ArrowStyle | None = None) -> None:
        """Draw a polyline or closed polygonal path through ``points``."""
        n = len(points)
        if n < 2:
            raise ValueError("failed to add line path. number of points should be >= 2.")
        segments = [[points[i], points[i + 1]] for i in range(n - 1)]
        self._strokeSegments(segments, color, thickness, closed, fill, opacity, directed, dashed, arrow_size, arrow_style)

    def addQuadraticPath(self, points: Sequence[Point], control_points: Sequence[Point], color: Color = 'black', thickness: Number = 1, closed: bool = False, fill: Color = 'none', opacity: Number = 1, directed: Directed = False, dashed: bool = False, arrow_size: Number = 1, *, arrow_style: ArrowStyle | None = None) -> None:
        """Draw a path made of quadratic Bezier segments."""
        num_points = len(points)
        num_control_points = len(control_points)
        if num_points - 1 != num_control_points or num_points < 2:
            raise ValueError("failed to add quadratic path")
        segments = [[points[i], control_points[i], points[i + 1]] for i in range(num_points - 1)]
        self._strokeSegments(segments, color, thickness, closed, fill, opacity, directed, dashed, arrow_size, arrow_style)
    
    def addCubicPath(self, points: Sequence[Point], control_points_1: Sequence[Point], control_points_2: Sequence[Point], color: Color = 'black', thickness: Number = 1, closed: bool = False, fill: Color = 'none', opacity: Number = 1, directed: Directed = False, dashed: bool = False, arrow_size: Number = 1, *, arrow_style: ArrowStyle | None = None) -> None:
        """Draw a path made of cubic Bezier segments."""
        num_points = len(points)
        num_control_points_1 = len(control_points_1)
        num_control_points_2 = len(control_points_2)

        if (num_points - 1 != num_control_points_1) or (num_points - 1 != num_control_points_2) \
            or num_control_points_1 != num_control_points_2 or num_points < 2:
            raise ValueError("failed to add cubic path")
        segments = [[points[i], control_points_1[i], control_points_2[i], points[i + 1]] for i in range(num_points - 1)]
        self._strokeSegments(segments, color, thickness, closed, fill, opacity, directed, dashed, arrow_size, arrow_style)

    def addCurve(self, points: Sequence[Point], color: Color = 'black', thickness: Number = 1, closed: bool = False, fill: Color = 'none', opacity: Number = 1, directed: Directed = False, dashed: bool = False, arrow_size: Number = 1, *, arrow_style: ArrowStyle | None = None) -> None:
        """Fit and draw a smooth cubic Bezier curve through the supplied points."""
        curve_points = list(points)
        a, b = self._fitBezierCurve(curve_points, closed=closed)
        if closed:
            self.addCubicPath(curve_points + [curve_points[0]], a, b, color=color, thickness=thickness, directed=directed, fill=fill, opacity=opacity, dashed=dashed, arrow_size=arrow_size, arrow_style=arrow_style)
        else:
            self.addCubicPath(curve_points, a, b, color=color, thickness=thickness, directed=directed, fill=fill, opacity=opacity, dashed=dashed, arrow_size=arrow_size, arrow_style=arrow_style)
    
    def addCircularArc(self, x: Number, y: Number, r: Number, theta1: Number, theta2: Number, color: Color = 'black', thickness: Number = 1, fill: Color = 'none', opacity: Number = 1, directed: Directed = False, dashed: bool = False, arrow_size: Number = 1, *, arrow_style: ArrowStyle | None = None) -> None:
        """Draw a circular SVG arc between two angles in degrees."""
        def point(theta: Number) -> Point:
            return (x + r * np.cos(theta * np.pi / 180), y + r * np.sin(theta * np.pi / 180))
        sgn = -1 if theta1 > theta2 else 1
        start, end = self._arrowEnds(directed)
        heads: list[tuple[Number, Number, Number]] = []
        arrow = None
        t1, t2 = theta1, theta2
        if start or end:
            style, scale, tip_back, line_back = self._arrowMetrics(thickness, arrow_size, arrow_style)
            arrow = (style, scale, tip_back)
            # Trim by arc length, keeping at least 10% of the sweep.
            trim = min(line_back / r * 180 / np.pi, 0.45 * abs(theta2 - theta1)) if r > 0 else 0
            if end:
                heads.append((*point(theta2), theta2 + 90 * sgn))
                t2 = theta2 - sgn * trim
            if start:
                heads.append((*point(theta1), theta1 - 90 * sgn))
                t1 = theta1 + sgn * trim
        (x1, y1), (x2, y2) = point(t1), point(t2)
        largeArcFlag = 1 if abs(t2 - t1) > 180 else 0
        sweepFlag = 0 if sgn < 0 else 1
        self._emitStroke(f'<path d="M {x1:.4f} {y1:.4f} A {r:.4f} {r:.4f} 0 {largeArcFlag} {sweepFlag} {x2:.4f} {y2:.4f}"', color, thickness, opacity, dashed, fill, heads, arrow)
    
    def _getRotShift(self, W: Number, H: Number, scale: Number, rot: Number, baseline: PositionBaseline, anchor: TextAnchor) -> Point:
        # Outputs how much we should shift a rectangle before applying rotation in order to obtain the same effect as changing the axis of rotation.
        # Useful for rotating latex equations.
        p = [0, 0]
        if baseline == "middle":
            p[1] = H/2
        elif baseline == "text-top":
            p[1] = H
        elif baseline == 'hanging':
            p[1] = 0
        else:
            raise ValueError(f"invalid baseline: {baseline}. supported baselines are: middle, text-top, hanging.")

        if anchor == "start":
            p[0] = 0
        elif anchor == "middle":
            p[0] = W/2
        elif anchor == "end":
            p[0] = W
        else:
            raise ValueError(f"invalid anchor: {anchor}. supported anchors are: start, middle, end.")

        if rot == 0:
            dx, dy = -p[0] * scale, -p[1] * scale
        else:
            if (p[0] != 0):
                angle = np.arctan(p[1] / p[0]) + rot * np.pi / 180
            else:
                angle = np.pi/2 + rot * np.pi / 180
            r = np.sqrt(p[0]**2 + p[1]**2)
            dx, dy = -r * np.cos(angle) * scale, -r * np.sin(angle) * scale
        return dx, dy

    def addLaTeX(self, tex: str, x: Number, y: Number, scale: Number = 1, rot: Number = 0, baseline: PositionBaseline = "middle", anchor: TextAnchor = "middle", color: Color = "black", backend: SvgBackend = "inkscape") -> None:
        """Render LaTeX math and embed it as an SVG subfigure."""
        # baseline: hanging, middle, text-top
        # anchor: start, middle, end
        svg, W, H = tex2svg(tex, self.curr_latex_eq_num, backend=backend, executables=self.executables)
        self.curr_latex_eq_num += 1
        dx, dy = self._getRotShift(W, H, scale, rot, baseline, anchor)
        if color == 'black':
            latex_color = ''
        else:
            latex_color = f'fill="{color}"'
            svg = self._replaceAttribute(svg, 'fill', color)
            svg = self._replaceAttribute(svg, 'stroke', color)
        self.contents.append(f'<g transform="translate({x+dx} {y+dy}) rotate({rot}) scale({scale})" {latex_color}>\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n{svg}\n</svg>\n</g>')
    
    def defineLinearGradient(self, grad_id: int | str, x1: Number = 0, y1: Number = 0, x2: Number = 1, y2: Number = 0, spread_method: GradientSpread = 'pad', stop_points: Sequence[Number] = (0, 1), stop_colors: Sequence[Color] = ('yellow', 'red'), stop_opacities: Sequence[Number] | None = None) -> None:
        """Define a reusable linear gradient in the canvas ``defs`` section."""
        # some basic checks:
        grad_id = str(grad_id)
        if grad_id in self.gradients:
            raise KeyError(f'a gradient with id {grad_id} is already defined')
        if len(stop_points) <= 1 or len(stop_colors) <= 1:
            raise ValueError('there should be atleast 2 stop points and stop colors')
        if len(stop_points) != len(stop_colors):
            raise ValueError('length of stop points and stop colors do not match')
        if (x1 > 1) or (y1 > 1) or (x2 > 1) or (y2 > 1) or (x1 < 0) or (x2 < 0) or (y1 < 0) or (y2 < 0):
            raise ValueError('x1, y1, x2, y2 should be >= 0 and <= 1')        
        for i, sp in enumerate(stop_points):
            if (sp > 1) or (sp < 0):
                raise ValueError(f'invalid stop point {sp} at index {i}: all stop points should be >= 0 and <= 1')
        if spread_method not in {"pad", "reflect", "repeat"}:
            raise ValueError(f'invalid spread method: {spread_method}, allowed spread methods are: pad, reflect and repeat')
        if stop_opacities is not None:
            if len(stop_opacities) != len(stop_points):
                raise ValueError('length of stop points and stop opacities do not match')

        # define the gradient:
        x1, y1, x2, y2 = 100 * x1, 100 * y1, 100 * x2, 100 * y2
        grad = [f'<linearGradient id="grad_{grad_id}" x1="{x1:.4f}%" y1="{y1:.4f}%" x2="{x2:.4f}%" y2="{y2:.4f}%">\n']
        if stop_opacities is None:
            for (stop_point, stop_color) in zip(stop_points, stop_colors):
                grad.append(f'<stop offset="{100*stop_point:.2f}%" stop-color="{stop_color}"/>\n')
        else:
            for (stop_point, stop_color, stop_opacity) in zip(stop_points, stop_colors, stop_opacities):
                grad.append(f'<stop offset="{100*stop_point:.2f}%" stop-color="{stop_color}" stop-opacity="{stop_opacity:.4f}"/>\n')
        
        grad.append('</linearGradient>')
        grad = ''.join(grad)
        self.defs.append(grad)
        self.gradients.add(grad_id)

    def defineRadialGradient(self, grad_id: int | str, cx: Number = 0.5, cy: Number = 0.5, fx: Number = 0.5, fy: Number = 0.5, r: Number = 0.5, spread_method: GradientSpread = 'pad', stop_points: Sequence[Number] = (0, 1), stop_colors: Sequence[Color] = ('yellow', 'red'), stop_opacities: Sequence[Number] | None = None) -> None:
        """Define a reusable radial gradient in the canvas ``defs`` section."""
        # some basic checks:
        grad_id = str(grad_id)
        if grad_id in self.gradients:
            raise KeyError(f'a gradient with id {grad_id} is already defined')
        if len(stop_points) <= 1 or len(stop_colors) <= 1:
            raise ValueError('there should be atleast 2 stop points and stop colors')
        if len(stop_points) != len(stop_colors):
            raise ValueError('length of stop points and stop colors do not match')
        if (cx > 1) or (cy > 1) or (fx > 1) or (fy > 1) or (cx < 0) or (cy < 0) or (fx < 0) or (fy < 0) or (r > 1) or (r < 0):
            raise ValueError('cx, cy, fx, fy, r should be >= 0 and <= 1')
        for i, sp in enumerate(stop_points):
            if (sp > 1) or (sp < 0):
                raise ValueError(f'invalid stop point {sp} at index {i}: all stop points should be >= 0 and <= 1')
        if spread_method not in {"pad", "reflect", "repeat"}:
            raise ValueError(f'invalid spread method: {spread_method}, allowed apread methods are: pad, reflect and repeat')
        if stop_opacities is not None:
            if len(stop_opacities) != len(stop_points):
                raise ValueError('length of stop points and stop opacities do not match')
            for i, op in enumerate(stop_opacities):
                if (op > 1) or (op < 0):
                    raise ValueError(f'invalid opacity {op} at index {i}: all opacities should be >= 0 and <= 1')

        # define the gradient:
        cx, cy, fx, fy, r = 100*cx, 100*cy, 100*fx, 100*fy, 100*r
        grad = [f'<radialGradient id="grad_{grad_id}" cx="{cx:.4f}%" cy="{cy:.4f}%" r="{r:.4f}%" fx="{fx:.4f}%" fy="{fy:.4f}%">']
        if stop_opacities is None:
            for (stop_point, stop_color) in zip(stop_points, stop_colors):
                grad.append(f'<stop offset="{100*stop_point:.2f}%" stop-color="{stop_color}"/>\n')
        else:
            for (stop_point, stop_color, stop_opacity) in zip(stop_points, stop_colors, stop_opacities):
                grad.append(f'<stop offset="{100*stop_point:.2f}%" stop-color="{stop_color}" stop-opacity="{stop_opacity:.4f}"/>\n')
        
        grad.append('</radialGradient>')
        grad = ''.join(grad)
        self.defs.append(grad)
        self.gradients.add(grad_id)

    def getGradient(self, grad_id: int | str) -> Color:
        """Return the SVG paint-server URL for a previously defined gradient."""
        grad_id = str(grad_id)
        if grad_id not in self.gradients:
            raise KeyError(f'no gradient defined with id: {grad_id}')
        return f'url(#grad_{grad_id})'

    def _renderParts(self) -> tuple[list[str], list[str], set[str]]:
        # Returns (defs, contents, used_fonts). Subclasses that compose other
        # canvases (e.g. Figure) override this to splice in their children.
        return list(self.defs), list(self.contents), set(self.used_fonts)

    def toSvg(self) -> str:
        """Return the complete SVG document as a string."""
        defs, contents, fonts = self._renderParts()
        file_contents = [f'<svg width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg">']
        font_css = self._fontFaceCss(fonts)
        if len(defs) > 0 or font_css:
            file_contents.append('<defs>')
            if font_css:
                file_contents.append(f'<style>\n{font_css}\n</style>')
            file_contents.extend(defs)
            file_contents.append('</defs>')
        file_contents.extend(contents)
        file_contents.append('</svg>')
        return '\n'.join(file_contents)

    def save(self, filename: str | os.PathLike[str]) -> None:
        """Write the accumulated SVG markup to ``filename``."""
        with open(filename, 'w', encoding="utf-8") as f:
            f.write(self.toSvg())
    
    def _findAttribute(self, svg_text: str, attribute: str) -> str:
        result = re.search(rf'{attribute}=(["\'])(.+?)\1', svg_text)
        return result.group(2)
    
    def _replaceAttribute(self, svg_text: str, attribute: str, new_value: Any) -> str:
        pattern = rf'({attribute}=["\'])(.+?)(["\'])'
        replacement = r"\1" + str(new_value) + r"\3"
        new_svg_text = re.sub(pattern, replacement, svg_text)
        return new_svg_text

    def export(self, filename: str | os.PathLike[str], export_type: ExportType = 'png', dpi: int = 200) -> None:
        """Export the canvas to PNG or PDF via Inkscape.

        Registered file-backed fonts are exposed to Inkscape through a
        temporary fontconfig setup (Inkscape ignores ``@font-face``), so the
        exported text uses the same fonts that were used to measure it.
        """
        if export_type not in {'png', 'pdf'}:
            raise ValueError(f'unexpected export type: {export_type}. supported export types are: png, pdf')

        _, _, fonts = self._renderParts()
        args = [f'--export-type={export_type}', f'--export-filename={os.fspath(filename)}']
        if export_type == 'png':
            args.append(f'--export-dpi={dpi}')
        with tempfile.TemporaryDirectory() as temp_dir:
            svg_path = os.path.join(temp_dir, 'tmp.svg')
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(self.toSvg())
            with inkscape_font_env([get_font(name) for name in sorted(fonts)], self.executables.inkscape) as env:
                try:
                    run([self.executables.inkscape, svg_path, *args], check=True, capture_output=True, env=env)
                except CalledProcessError as e:
                    raise RuntimeError(f"inkscape failed to export the figure : {e.stderr.decode(errors='ignore')}")

    def _computeIntersection(self, x: Number, y: Number, theta: Number, x1: Number, y1: Number, x2: Number, y2: Number) -> tuple[Number | None, Number | None]:
        # computes the point of intersection of two lines: (1) <x + r*cos(theta), y + r*sin(theta)> ; (2) <t*x1 + (1-t)*x2, t*y1 + (1-t)*y2>
        # returns r, t
        theta *= np.pi/180
        det = -np.cos(theta) * (y1-y2) + np.sin(theta) * (x1-x2)
        if det == 0:
            return (None, None)
        r = ((x-x2) * (y1-y2) - (y-y2) * (x1-x2)) / det
        t = (-np.cos(theta) * (y-y2) + np.sin(theta) * (x-x2)) / det
        return (r, t)
    
    def _isConvexPolygon(self, points: Sequence[Point]) -> bool:
        # checks whether a polygon specified by a list of points is convex
        if len(points) < 3:
            return False
        n = len(points)
        signs = [0] * n
        for i in range(n):
            A = points[(i-1)%n]
            B = points[i]
            C = points[(i+1)%n]
            cross_prod = (B[0] - A[0]) * (C[1] - B[1]) - (B[1] - A[1]) * (C[0] - B[0])
            signs[i] = np.sign(cross_prod)
        first = 0
        for i in range(n):
            if (signs[i] != 0):
                if (first == 0):
                    first = signs[i]
                else:
                    if (first != signs[i]):
                        return False
        if (first == 0):
            return False
        else:
            return True
    
    def _defSubFigure(self, sub_fig_id: int | str, sub_fig_view_box: Sequence[Number], sub_fig_svg: str) -> None:
        sub_fig_id = str(sub_fig_id)
        if sub_fig_id in self.sub_figs:
            raise KeyError(f"sub figure id {sub_fig_id} already exists")
        self.sub_figs.add(sub_fig_id)
        (w1, h1, W, H) = sub_fig_view_box
        vb = f"{w1} {h1} {W} {H}"
        self.sub_fig_dims[sub_fig_id] = (W, H)
        self.defs.append(f'<g id="fig_{sub_fig_id}">\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="{vb}">\n{sub_fig_svg}\n</svg>\n</g>')
    
    def importSvgFromFile(self, file_name: str | os.PathLike[str], fig_id: int | str) -> None:
        """Import an SVG file into ``defs`` so it can be placed with :meth:`addSubFig`."""
        (svg, vb) = import_svg_from_file(file_name, fig_id)
        self._defSubFigure(fig_id, vb, svg)
    
    def addSubFig(self, fig_id: int | str, x: Number, y: Number, scale: Number = 1, rot: Number = 0, baseline: PositionBaseline = "middle", anchor: TextAnchor = "middle", flip: bool = False) -> None:
        """Place a previously imported subfigure on the canvas."""
        # baseline: hanging, middle, text-top
        # anchor: start, middle, end
        fig_id = str(fig_id)
        if fig_id not in self.sub_figs:
            raise KeyError(f"sub figure {fig_id} is not defined")
        
        (W, H) = self.sub_fig_dims[fig_id]
        dx, dy = self._getRotShift(W, H, scale, rot, baseline, anchor)
        x += dx
        y += dy
        
        if flip:
            scale_x = -scale
            scale_y = scale
            x += W * np.cos(rot * np.pi / 180) * scale
            y += W * np.sin(rot * np.pi / 180) * scale
        else:
            scale_x = scale
            scale_y = scale
        
        self.contents.append(f'<use xlink:href="#fig_{fig_id}" transform="translate({x:.4f} {y:.4f}) rotate({rot:.4f}) scale({scale_x:.4f} {scale_y:.4f})"/>')
    
    def _computeInteresctionWithConvexPolygon(self, x: Number, y: Number, theta: Number, points: Sequence[Point]) -> Point:
        # Computes the point of intersection of the ray: <x+r*cos(theta), y+r*sin(theta) | r >= 0> with the polygon defined by the given points.
        # Returns the point of intersection:
        angles = {p : self._getRot(x, y, p[0], p[1]) for p in points}
        points = sorted(points, key=lambda x: angles[x])

        # check if the polygon is convex
        if not self._isConvexPolygon(points):
            raise ValueError('not a convex polygon')
        
        theta = (theta + 90) % (360) - 90
        n = len(points)
        for i in range(n):
            if (angles[points[i]] <= theta <= angles[points[(i+1)%n]]):
                break
        (_, t) = self._computeIntersection(x, y, theta, *points[i], *points[(i+1)%n])
        a = t * points[i][0] + (1-t) * points[(i+1)%n][0]
        b = t * points[i][1] + (1-t) * points[(i+1)%n][1]
        return (a, b)

    def _fitBezierCurve(self, points: Sequence[Point], closed: bool = False) -> tuple[list[Point], list[Point]]:
        # Control points (a_i, b_i) of a C2-continuous cubic Bezier spline whose
        # i-th segment runs P_i -> a_i -> b_i -> P_{i+1}.
        #   C1 at each knot:  a_i + b_{i-1} = 2 P_i
        #   C2 at each knot:  a_{i-1} + 4 a_i + a_{i+1} = 4 P_i + 2 P_{i+1}
        # Open curves use natural end conditions (zero curvature at both ends);
        # closed curves are periodic, so the seam is as smooth as any other knot.
        P = np.asarray([(float(x), float(y)) for (x, y) in points])
        m = len(P)
        if closed:
            if m < 3:
                raise ValueError("a closed curve needs at least 3 points")
            A = 4 * np.identity(m)
            for i in range(m):
                A[i, (i - 1) % m] = 1
                A[i, (i + 1) % m] = 1
            P_next = np.roll(P, -1, axis=0)
            a = np.linalg.solve(A, 4 * P + 2 * P_next)
            b = 2 * P_next - np.roll(a, -1, axis=0)
        else:
            if m < 2:
                raise ValueError("a curve needs at least 2 points")
            n = m - 1  # number of segments
            if n == 1:
                a = P[:1] + (P[1:] - P[:1]) / 3
                b = P[:1] + 2 * (P[1:] - P[:1]) / 3
            else:
                A = 4 * np.identity(n)
                np.fill_diagonal(A[1:], 1)
                np.fill_diagonal(A[:, 1:], 1)
                A[0, 0] = 2
                A[n-1, n-1] = 7
                A[n-1, n-2] = 2
                rhs = 4 * P[:n] + 2 * P[1:]
                rhs[0] = P[0] + 2 * P[1]
                rhs[n-1] = 8 * P[n-1] + P[n]
                a = np.linalg.solve(A, rhs)
                b = np.empty_like(a)
                b[:n-1] = 2 * P[1:n] - a[1:]
                b[n-1] = (a[n-1] + P[n]) / 2
        return [tuple(p) for p in a], [tuple(p) for p in b]

class PlotStyle:
    """Font sizes and font-relative spacing shared by a plot's text elements.

    Every gap is expressed as a fraction of the font size of the text it
    separates, so layouts stay balanced when font sizes change:

    * ``tick_pad``: gap between the outer end of a tick notch and its label,
      in units of ``tick_size``.
    * ``label_pad``: gap between the outer edge of the tick labels and the
      axis label, in units of ``label_size``.
    * ``title_pad``: gap between the top of the plot area and the title, in
      units of ``title_size``.
    * ``outer_pad``: blank border (user units) kept around the content when
      margins are computed automatically (``origin="auto"`` / ``margins="auto"``).
    * ``tick_length``: total length of a tick notch (drawn centred on the axis).
    """

    def __init__(self, tick_size: Number = 16, label_size: Number = 16, title_size: Number = 18, *, tick_length: Number = 10, tick_pad: Number = 0.35, label_pad: Number = 0.5, title_pad: Number = 0.6, outer_pad: Number = 8, line_height: Number = 1.2) -> None:
        self.tick_size = tick_size
        self.label_size = label_size
        self.title_size = title_size
        self.tick_length = tick_length
        self.tick_pad = tick_pad
        self.label_pad = label_pad
        self.title_pad = title_pad
        self.outer_pad = outer_pad
        self.line_height = line_height

    @classmethod
    def scaled(cls, base_size: Number = 16, **overrides: Any) -> "PlotStyle":
        """Build a style from one base font size (ticks = base, labels = base, title = 1.15 x base)."""
        sizes = dict(tick_size=base_size, label_size=base_size, title_size=round(1.15 * base_size, 2), tick_length=round(0.625 * base_size, 2))
        sizes.update(overrides)
        return cls(**sizes)

    def copy(self, **overrides: Any) -> "PlotStyle":
        """Return a copy with some attributes replaced."""
        values = dict(self.__dict__)
        values.update(overrides)
        return PlotStyle(**values)

    def __repr__(self) -> str:
        args = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'PlotStyle({args})'


class Plot(Canvas):
    """Canvas with helpers for drawing simple 2D plots."""

    def __init__(self, height: Number, width: Number, origin: Point | Literal["auto"] | None = "auto", margins: Point | Literal["auto"] | None = "auto", x_range: Point = (0, 1), y_range: Point = (0, 1), *, style: PlotStyle | None = None, extra_margins: Sequence[Number] = (0, 0, 0, 0), executables: ExecutablePaths | None = None) -> None:
        """Create a plotting canvas with data-to-canvas coordinate mapping.

        ``origin`` is the canvas position of the bottom-left corner of the plot
        area and ``margins`` the ``(right, top)`` space left around it. Both
        default to ``"auto"``: they are sized from the fonts in ``style`` so
        tick labels, axis labels and the title fit. ``None`` restores the
        legacy percentage-based layout (15%/15% left/bottom, 10%/10% right/top).
        ``extra_margins`` = ``(left, bottom, right, top)``
        is added on top of the automatic margins (e.g. room for rotated tick labels).
        """
        Canvas.__init__(self, height, width, executables=executables)
        self.style = style if style is not None else PlotStyle()
        (self._x, self.x_) = x_range # the values on the x axis will range between [_x, x_]
        (self._y, self.y_) = y_range # the values on the y axis will range between [_y, y_]
        self._extra_margins = tuple(extra_margins)
        self._setLayout(origin, margins)
        self.is_cross_def_included = False
        self.is_square_def_included = False
        self.legend_items = []
        # Distance from each axis line to the outer edge of its tick labels;
        # used to place axis labels automatically. None until ticks are drawn.
        self._tick_extent: dict[str, float | None] = {'x': None, 'y': None}

    def _setLayout(self, origin: Point | Literal["auto"] | None, margins: Point | Literal["auto"] | None) -> None:
        width, height = self.width, self.height
        if origin == "auto" or margins == "auto":
            auto_left, auto_bottom, auto_right, auto_top = self._autoMargins()
        if origin is None:
            self.O_x = 0.15 * width
            self.O_y = 0.85 * height
        elif origin == "auto":
            self.O_x = auto_left
            self.O_y = height - auto_bottom
        else:
            (self.O_x, self.O_y) = origin # this is where the bottom left corner of our plot will be positioned on the canvas
        if margins is None:
            self.m_x = 0.1 * width
            self.m_y = 0.1 * height
        elif margins == "auto":
            self.m_x = auto_right
            self.m_y = auto_top
        else:
            (self.m_x, self.m_y) = margins # this is how much space will be left out on the right hand side and on the top
        if (origin == "auto" or margins == "auto") and (self.O_x >= width - self.m_x or self.m_y >= self.O_y):
            warnings.warn(f"the {width}x{height} canvas is too small for automatic margins with the current font sizes; falling back to percentage margins (pass origin/margins or a smaller PlotStyle)", stacklevel=3)
            self._setLayout(None if origin == "auto" else origin, None if margins == "auto" else margins)

    def _autoMargins(self) -> tuple[float, float, float, float]:
        # Estimates (left, bottom, right, top) margins that fit tick labels,
        # axis labels and a title, using the sizes in self.style. Tick label
        # widths are estimated from the axis range formatted like easyTicks.
        s = self.style
        font = self.default_font
        tick_out = s.tick_length / 2
        def label_width(v: Number) -> float:
            return text_width(f'{v:.2f}', s.tick_size, font)
        ytick_w = max(label_width(self._y), label_width(self.y_))
        left = s.outer_pad + s.label_size + s.label_pad * s.label_size + ytick_w + s.tick_pad * s.tick_size + tick_out
        bottom = s.outer_pad + s.label_size + s.label_pad * s.label_size + s.tick_size + s.tick_pad * s.tick_size + tick_out
        right = s.outer_pad + max(label_width(self.x_) / 2, s.outer_pad)
        top = s.outer_pad + s.line_height * s.title_size + s.title_pad * s.title_size
        extra_left, extra_bottom, extra_right, extra_top = getattr(self, '_extra_margins', (0, 0, 0, 0))
        return left + extra_left, bottom + extra_bottom, right + extra_right, top + extra_top

    def _blockSize(self, text: Any, size: Number) -> tuple[float, float]:
        # Measured (width, height) of an unrotated text block. A single line is
        # taken to be ~1 em tall (ascender to descender of the glyphs).
        lines = self._textLines(text, size, self.default_font, False, False, None)
        width = max((text_width(line, size, self.default_font) for line in lines), default=0.0)
        height = size * (1 + self.style.line_height * (len(lines) - 1))
        return width, height

    def _recordTickExtent(self, axis: str, extent: float) -> None:
        prev = self._tick_extent[axis]
        self._tick_extent[axis] = extent if prev is None else max(prev, extent)

    def tickExtent(self, axis: Literal["x", "y"]) -> float:
        """Distance from the x or y axis to the outer edge of its tick labels.

        Falls back to the outward half of a default tick notch if no tick
        labels have been drawn on that axis yet.
        """
        extent = self._tick_extent[axis]
        return self.style.tick_length / 2 if extent is None else extent

    def mapToCanvas(self, x: Number, y: Number) -> Point:
        """Map a data-space point to canvas coordinates."""
        # this function maps where the data point (x, y) will lie on the canvas
        alpha = (x - self._x) / (self.x_ - self._x)
        beta = (y - self._y) / (self.y_ - self._y)
        x_canvas = self.O_x * (1 - alpha) + (self.width - self.m_x) * alpha
        y_canvas = self.O_y * (1 - beta) + self.m_y * beta
        return (x_canvas, y_canvas)

    def putMarker(self, x: Number, y: Number, marker_type: MarkerType = 'circle', size: Number = 1, color: Color = 'red', on_canvas: bool = True) -> None:
        """Draw a marker at a data-space or canvas-space point."""
        if on_canvas:
            (x, y) = self.mapToCanvas(x, y)
        if marker_type == 'circle':
            self.addCircle(x, y, 5 * size, color, 'none')
        elif marker_type == 'cross':
            if not self.is_cross_def_included:
                self.defs.append('<path id="cross" d="M-5 5 L5 -5 M5 5 L-5 -5"/>')
                self.is_cross_def_included = True
            self.contents.append(f'<use xlink:href="#cross" transform="translate({x:.4f} {y:.4f}) scale({size:.4f} {size:.4f})" stroke="{color}" stroke-width="2" fill="none"/>')
        elif marker_type == 'square':
            if not self.is_square_def_included:
                self.defs.append('<rect id="square" height="9" width="9" x="-4.5" y="-4.5"/>')
                self.is_square_def_included = True
            self.contents.append(f'<use xlink:href="#square" transform="translate({x:.4f} {y:.4f}) scale({size:.4f} {size:.4f})" stroke="none" fill="{color}"/>')
        else:
            raise ValueError(f"invalid marker type {marker_type}: supported markers are: circle, cross, square")

    def addAxes(self, color: Color = "black", thickness: Number = 1, directed: bool = False) -> None:
        """Draw x and y axes for the plot area."""
        self.addLine(x1 = self.O_x, x2 = self.O_x, y2 = 2 * self.m_y / 3, y1 = self.O_y + self.m_y / 10, color = color, thickness = thickness, directed=directed)
        self.addLine(y1 = self.O_y, y2 = self.O_y, x1 = self.O_x - self.m_x / 10, x2 = self.width - 2 * self.m_x / 3, color = color, thickness = thickness, directed=directed)

    def addTicksX(self, labels: Iterable[tuple[Number, Any]], color: Color = "black", notch_thickness: Number = 2, notch_length: Number | None = None, rotation: Number = 0, text_anchor: TextAnchor | None = None, text_size: Number | None = None, grid: bool = True, *, pad: Number | None = None) -> None:
        """Add x-axis tick labels and optional vertical grid lines.

        Labels are placed ``pad`` below the outer end of the notch (default:
        ``style.tick_pad`` x font size). Rotated labels are anchored at their
        end (negative rotation) or start (positive rotation) so they hang off
        the tick without overlapping the axis. ``text_size``/``notch_length``
        default to the plot's :class:`PlotStyle`.
        """
        size = self.style.tick_size if text_size is None else text_size
        notch_length = self.style.tick_length if notch_length is None else notch_length
        pad = self.style.tick_pad * size if pad is None else pad
        offset = notch_length / 2 + pad
        theta = np.deg2rad(rotation)
        sin_t, cos_t = np.sin(theta), abs(np.cos(theta))
        extent = offset
        for x, label in labels:
            (x_tick, y_tick) = self.mapToCanvas(x, self._y)
            w, h = self._blockSize(label, size)
            if abs(sin_t) < 1e-9:
                anchor, baseline, y_text = (text_anchor or "middle"), "hanging", y_tick + offset
                extent = max(extent, offset + h)
            else:
                # The label's text-centre line passes through the anchor point;
                # shift down so the corner nearest the axis sits at `offset`.
                anchor = text_anchor or ("end" if sin_t < 0 else "start")
                baseline, y_text = "middle", y_tick + offset + cos_t * h / 2
                extent = max(extent, offset + w * abs(sin_t) + h * cos_t)
            self.addText(label, x = x_tick, y = y_text, color = color, rotation = rotation, baseline = baseline, anchor = anchor, size = size)
            if x != self._x:
                self.addLine(x1 = x_tick, x2 = x_tick, y1 = y_tick - notch_length / 2, y2 = y_tick + notch_length / 2, color = color, thickness = notch_thickness)
                if grid:
                    self.addLine(x1 = x_tick, x2 = x_tick, y1 = self.O_y, y2 = self.m_y, color = "gray", thickness = 1, dashed = True)
        self._recordTickExtent('x', extent)

    def addTicksY(self, labels: Iterable[tuple[Number, Any]], color: Color = "black", notch_thickness: Number = 2, notch_length: Number | None = None, rotation: Number = 0, text_baseline: TextBaseline = "middle", text_size: Number | None = None, grid: bool = True, *, pad: Number | None = None) -> None:
        """Add y-axis tick labels and optional horizontal grid lines.

        Labels end ``pad`` to the left of the outer end of the notch (default:
        ``style.tick_pad`` x font size). Rotated labels are centred on the tick
        with their rotated bounding box kept clear of the axis.
        """
        size = self.style.tick_size if text_size is None else text_size
        notch_length = self.style.tick_length if notch_length is None else notch_length
        pad = self.style.tick_pad * size if pad is None else pad
        offset = notch_length / 2 + pad
        theta = np.deg2rad(rotation)
        sin_t, cos_t = abs(np.sin(theta)), abs(np.cos(theta))
        extent = offset
        for y, label in labels:
            (x_tick, y_tick) = self.mapToCanvas(self._x, y)
            w, h = self._blockSize(label, size)
            if sin_t < 1e-9:
                self.addText(label, y = y_tick, x = x_tick - offset, color = color, rotation = rotation, baseline = text_baseline, anchor = "end", size = size)
                extent = max(extent, offset + w)
            else:
                box_w = w * cos_t + h * sin_t
                self.addText(label, y = y_tick, x = x_tick - offset - box_w / 2, color = color, rotation = rotation, baseline = "middle", anchor = "middle", size = size)
                extent = max(extent, offset + box_w)
            if y != self._y:
                self.addLine(y1 = y_tick, y2 = y_tick, x1 = x_tick - notch_length / 2, x2 = x_tick + notch_length / 2, color = color, thickness = notch_thickness)
                if grid:
                    self.addLine(y1 = y_tick, y2 = y_tick, x1 = self.O_x, x2 = self.width - self.m_x, color = "gray", thickness = 1, dashed = True)
        self._recordTickExtent('y', extent)

    def addBar(self, x: Number, y: Number, bar_width: Number, _y: Number = 0, bar_color: Color = "orange", opacity: Number = 1) -> None:
        """Draw a single vertical bar from ``_y`` to ``y``."""
        (x1, y1) = self.mapToCanvas(x, _y)
        (_, y2) = self.mapToCanvas(x, y)
        self.addRectangle(height=y1-y2, width=bar_width, x=(x1-bar_width/2), y=y2, color=bar_color, border='none', opacity=opacity)

    def addAxisLabels(self, xlabel: str | None = None, ylabel: str | None = None, xsize: Number | None = None, ysize: Number | None = None, color: Color = "black", xpad: Number | None = None, ypad: Number | None = None, xrot: Number = 0, yrot: Number = 0, xlatex: bool = False, ylatex: bool = False) -> None:
        """Add optional x- and y-axis labels.

        By default labels are placed just outside the tick labels already
        drawn on that axis (plus ``style.label_pad`` x font size), so call this
        after ``addTicksX``/``addTicksY``/``easyTicks``. ``xpad`` overrides the
        distance from the x axis to the top of the x label; ``ypad`` overrides
        the distance from the y axis to the centre line of the y label.
        """
        xsize = self.style.label_size if xsize is None else xsize
        ysize = self.style.label_size if ysize is None else ysize

        if xlabel is not None:
            if xpad is None:
                xpad = self.tickExtent('x') + self.style.label_pad * xsize
            x_mid, y_axis = self.mapToCanvas((self._x + self.x_)/2, self._y)
            y = y_axis + xpad
            if not xlatex and y + self._blockSize(xlabel, xsize)[1] > self.height + 0.5:
                warnings.warn(f"x axis label {xlabel!r} extends below the canvas; increase the bottom margin (e.g. extra_margins=(0, 30, 0, 0) with auto margins, or an explicit origin) or reduce font sizes", stacklevel=2)
            if xlatex:
                self.addLaTeX(xlabel, x_mid, y, baseline="hanging", anchor="middle", scale=(xsize/16), rot=xrot)
            else:
                self.addText(xlabel, x_mid, y, color=color, rotation=xrot, baseline="hanging", anchor="middle", size=xsize)

        if ylabel is not None:
            x_axis, y_mid = self.mapToCanvas(self._x, (self._y + self.y_)/2)
            edge = self.tickExtent('y') + self.style.label_pad * ysize  # axis -> near edge of the label
            if ylatex:
                if ypad is None:
                    # "text-top" pins the bottom of the rendered box (which faces the axis after the -90 deg rotation).
                    self.addLaTeX(ylabel, x_axis - edge, y_mid, baseline="text-top", anchor="middle", scale=(ysize/16), rot=(yrot-90))
                else:
                    self.addLaTeX(ylabel, x_axis - ypad, y_mid, baseline="middle", anchor="middle", scale=(ysize/16), rot=(yrot-90))
            else:
                if ypad is None:
                    _, h = self._blockSize(ylabel, ysize)
                    ypad = edge + h / 2
                    if x_axis - ypad - h / 2 < -0.5:
                        warnings.warn(f"y axis label {ylabel!r} extends past the left edge of the canvas; increase the left margin (e.g. extra_margins=(30, 0, 0, 0) with auto margins, or an explicit origin) or reduce font sizes", stacklevel=2)
                self.addText(ylabel, x_axis - ypad, y_mid, color=color, rotation=(yrot-90), baseline="middle", anchor="middle", size=ysize)

    def addTitle(self, title: str, size: Number | None = None, color: Color = "black", pad: Number | None = None, latex: bool = False) -> None:
        """Add a title ``pad`` above the plot area (default: ``style.title_pad`` x size)."""
        size = self.style.title_size if size is None else size
        pad = self.style.title_pad * size if pad is None else pad
        x_mid, y_top = self.mapToCanvas((self._x + self.x_)/2, self.y_)
        y = y_top - pad
        if latex:
            self.addLaTeX(title, x_mid, y, scale=size/16, baseline="text-top")
        else:
            self.addText(title, x_mid, y, color=color, size=size, baseline="auto", anchor="middle")

    def addPlot(self, x: Iterable[Number], y: Iterable[Number], color: Color = "blue", thickness: Number = 1, interp: bool = False, opacity: Number = 1, dashed: bool = False, label: str | None = None) -> None:
        """Draw a line plot from paired x and y data."""
        arr = []
        for (a, b) in zip(x, y):
            arr.append(self.mapToCanvas(a, b))
        
        if interp:
            self.addCurve(arr, color, thickness, opacity=opacity, dashed=dashed)
        else:
            self.addLinePath(arr, color, thickness, opacity=opacity, dashed=dashed)
        
        if label is not None:
            self.legend_items.append((label, {'type': 'plot', 'color': color, 'thickness': thickness, 'opacity': opacity, 'dashed': dashed}))
    
    def addScatterPlot(self, x: Iterable[Number], y: Iterable[Number], color: Color = "blue", marker_type: MarkerType = "circle", marker_scale: Number = 1, label: str | None = None) -> None:
        """Draw a scatter plot from paired x and y data."""
        for (a, b) in zip(x, y):
            self.putMarker(a, b, marker_type, marker_scale, color)
        
        if label is not None:
            self.legend_items.append((label, {'type': 'scatter', 'color': color, 'marker_type': marker_type, 'marker_scale': marker_scale}))
    
    def addBarPlot(self, x: Iterable[Number], y: Iterable[Number], _y: Iterable[Number] | None = None, color: Color = "orange", bar_width: Number = 20, label: str | None = None) -> None:
        """Draw a bar plot, optionally with per-bar baselines."""
        if _y is None:
            for (a, b) in zip(x, y):
                self.addBar(a, b, bar_width, bar_color=color, _y=self._y)
        else:
            for (a, b, c) in zip(x, y, _y):
                self.addBar(a, b, bar_width, bar_color=color, _y=c)
        
        if label is not None:
            self.legend_items.append((label, {'type': 'bar', 'marker_type': 'square', 'marker_scale': 1, 'color': color}))
    
    def _computeLegendPosition(self, legend_width: Number, legend_height: Number, anchor: LegendAnchor = 'NE') -> Point:
        if anchor == 'NE':
            ax = self._x + (self.x_ - self._x) * 0.95
            ay = self._y + (self.y_ - self._y) * 0.95
            (ax, ay) = self.mapToCanvas(ax, ay)
            ax -= legend_width 
        elif anchor == 'N':
            ax = self._x + (self.x_ - self._x) * 0.5
            ay = self._y + (self.y_ - self._y) * 0.95
            (ax, ay) = self.mapToCanvas(ax, ay)
            ax -= legend_width/2
        elif anchor == 'NW':
            ax = self._x + (self.x_ - self._x) * 0.05
            ay = self._y + (self.y_ - self._y) * 0.95
            (ax, ay) = self.mapToCanvas(ax, ay)
        elif anchor == 'W':
            ax = self._x + (self.x_ - self._x) * 0.05
            ay = self._y + (self.y_ - self._y) * 0.5
            (ax, ay) = self.mapToCanvas(ax, ay)
            ay -= legend_height/2
        elif anchor == 'SW':
            ax = self._x + (self.x_ - self._x) * 0.05
            ay = self._y + (self.y_ - self._y) * 0.05
            (ax, ay) = self.mapToCanvas(ax, ay)
            ay -= legend_height
        elif anchor == 'S':
            ax = self._x + (self.x_ - self._x) * 0.5
            ay = self._y + (self.y_ - self._y) * 0.05
            (ax, ay) = self.mapToCanvas(ax, ay)
            ax -= legend_width/2
            ay -= legend_height
        elif anchor == 'SE':
            ax = self._x + (self.x_ - self._x) * 0.95
            ay = self._y + (self.y_ - self._y) * 0.05
            (ax, ay) = self.mapToCanvas(ax, ay)
            ax -= legend_width
            ay -= legend_height
        elif anchor == 'E':
            ax = self._x + (self.x_ - self._x) * 0.95
            ay = self._y + (self.y_ - self._y) * 0.5
            (ax, ay) = self.mapToCanvas(ax, ay)
            ax -= legend_width
            ay -= legend_height/2
        else:
            raise ValueError(f"invalid legend anchor: {anchor}. supported anchor types are: 'NE', 'N', 'NW', 'W', 'E', 'SW', 'S', 'SE'")
        return (ax, ay)
        
    def addLegend(self, anchor: LegendAnchor | None = 'NE', text_size: Number | None = None, text_color: Color = 'black', marker_scale: Number = 1, box_color: Color = 'yellow', box_border_color: Color = 'red', box_opacity: Number = 0.5, position: Point | None = None) -> None:
        """Draw a legend from the labels registered by plot methods."""
        text_size = self.style.tick_size if text_size is None else text_size
        self.legend_items.sort(key=lambda x: x[1]['type'])
        lines = [x[0] for x in self.legend_items]

        line_widths = [text_width(line, text_size, self.default_font) for line in lines]
        legend_width = max(line_widths) + 20 * marker_scale
        legend_height = len(lines) * 1.2 * text_size
        
        if (anchor == None) or (position is not None):
            (x, y) = position
        else:
            x, y = self._computeLegendPosition(legend_width, legend_height, anchor)
        x_text = x + 15 * marker_scale
        y_text = y + 0.6 * text_size
        self.addRectangle(legend_height, legend_width, x - 5 * marker_scale, y, color=box_color, border=box_border_color, thickness=2, opacity=box_opacity, corner_radius=10)
        
        # valign="top" keeps the first line centred on y_text and grows downward,
        # matching the per-item marker positions computed below.
        self.addText(
            lines,
            x_text,
            y_text,
            text_color,
            size=text_size,
            anchor="start",
            fit_width=True,
            valign="top",
        )
        for i, (_, plot_info) in enumerate(self.legend_items):
            y_item = y_text + i * 1.2 * text_size
            if plot_info['type'] == 'plot':
                x1 = x + 10 * marker_scale
                self.addLine(x, y_item, x1, y_item, color=plot_info['color'], thickness=plot_info['thickness'], dashed=plot_info['dashed'], opacity=plot_info['opacity'])
            elif (plot_info['type'] == 'scatter') or (plot_info['type']=='bar'):
                x1 = x + 5 * marker_scale
                self.putMarker(x1, y_item, marker_type=plot_info['marker_type'], size=marker_scale, color=plot_info['color'], on_canvas=False)
    
    def easyTicks(self, color: Color = 'black', ticks_per_unit: Number = 0.01, notch_thickness: Number = 2, notch_length: Number | None = None, rot_x: Number = 0, rot_y: Number = 0, text_size: Number | None = None, grid: bool = False) -> None:
        """Automatically choose and draw evenly spaced ticks."""
        (x1, y1) = self.mapToCanvas(self._x, self._y)
        (x2, y2) = self.mapToCanvas(self.x_, self.y_)
        X = x2 - x1
        Y = y1 - y2
        ticks_per_unit = max(min(ticks_per_unit, 0.05), 0.005)
        num_x_ticks = int(round(X * ticks_per_unit))
        num_y_ticks = int(round(Y * ticks_per_unit))
        
        if num_x_ticks > 0:
            x_ticks = np.linspace(self._x, self.x_, num=num_x_ticks)
            x_labels = [(x, f'{x:.2f}') for x in x_ticks]
            self.addTicksX(x_labels, color, notch_thickness, notch_length, rot_x, None, text_size, grid)
        if num_y_ticks > 0:
            y_ticks = np.linspace(self._y, self.y_, num=num_y_ticks)
            y_labels = [(y, f'{y:.2f}') for y in y_ticks]
            self.addTicksY(y_labels, color, notch_thickness, notch_length, rot_y, "middle", text_size, grid)
    
    def easyAxes(self, color: Color = 'black', thickness: Number = 2, directed: bool = True, ticks_per_unit: Number = 0.01, notch_length: Number | None = None, rot_x: Number = 0, rot_y: Number = 0, text_size: Number | None = None, grid: bool = False) -> None:
        """Draw axes and automatically chosen ticks."""
        self.addAxes(color, thickness, directed)
        self.easyTicks(color, ticks_per_unit, thickness, notch_length, rot_x, rot_y, text_size, grid)

class _SubplotSlot:
    # Placeholder stored in Figure.contents marking where (in z-order) a
    # subplot is rendered.
    __slots__ = ("plot", "x", "y", "index")

    def __init__(self, plot: Plot, x: float, y: float, index: int) -> None:
        self.plot, self.x, self.y, self.index = plot, x, y, index


class Figure(Canvas):
    """A canvas holding a grid of :class:`Plot` subplots.

    The figure area (minus ``padding`` and an optional title band) is split
    into ``rows`` x ``cols`` cells separated by ``wspace``/``hspace``. Each
    call to :meth:`subplot` returns an ordinary :class:`Plot` sized to its
    cell(s) and drawn in its own local coordinates; on save, every subplot is
    translated into place and its SVG ids are prefixed so markers, gradients,
    LaTeX glyphs, etc. never collide. The figure is itself a :class:`Canvas`,
    so you can draw annotations (e.g. arrows between subplots) in figure
    coordinates; use :meth:`mapToFigure` to convert subplot data coordinates.

    ``style`` is the default :class:`PlotStyle` for all subplots. Subplots
    use ``origin="auto"``/``margins="auto"`` by default so that subplots
    sharing a style get identical, aligned plot areas.
    """

    def __init__(self, height: Number, width: Number, rows: int = 1, cols: int = 1, *, title: str | None = None, title_size: Number | None = None, style: PlotStyle | None = None, wspace: Number = 10, hspace: Number = 10, padding: Number = 10, width_ratios: Sequence[Number] | None = None, height_ratios: Sequence[Number] | None = None, executables: ExecutablePaths | None = None) -> None:
        """Create a figure with a ``rows`` x ``cols`` subplot grid."""
        Canvas.__init__(self, height, width, executables=executables)
        if rows < 1 or cols < 1:
            raise ValueError("rows and cols must both be >= 1")
        width_ratios = [1] * cols if width_ratios is None else list(width_ratios)
        height_ratios = [1] * rows if height_ratios is None else list(height_ratios)
        if len(width_ratios) != cols or len(height_ratios) != rows:
            raise ValueError("width_ratios must have `cols` entries and height_ratios must have `rows` entries")
        if min(width_ratios) <= 0 or min(height_ratios) <= 0:
            raise ValueError("width/height ratios must be positive")
        self.rows, self.cols = rows, cols
        self.style = style if style is not None else PlotStyle()
        self._slots: list[_SubplotSlot] = []
        self._occupied: dict[tuple[int, int], int] = {}

        top = padding
        if title is not None:
            size = round(1.25 * self.style.title_size, 2) if title_size is None else title_size
            _, h = self.addText(title, width / 2, top, size=size, baseline="hanging", valign="top")
            top += h + self.style.title_pad * size
        grid_w = width - 2 * padding - wspace * (cols - 1)
        grid_h = height - top - padding - hspace * (rows - 1)
        if grid_w <= 0 or grid_h <= 0:
            raise ValueError("figure is too small for the requested padding/spacing")
        col_w = [grid_w * r / sum(width_ratios) for r in width_ratios]
        row_h = [grid_h * r / sum(height_ratios) for r in height_ratios]
        self._col_x = [padding + sum(col_w[:i]) + wspace * i for i in range(cols)]
        self._row_y = [top + sum(row_h[:i]) + hspace * i for i in range(rows)]
        self._col_w, self._row_h = col_w, row_h
        self.wspace, self.hspace = wspace, hspace

    def cellBox(self, row: int, col: int, rowspan: int = 1, colspan: int = 1) -> tuple[float, float, float, float]:
        """Return ``(x, y, width, height)`` of a (possibly spanning) grid cell in figure coordinates."""
        if rowspan < 1 or colspan < 1:
            raise ValueError("rowspan and colspan must be >= 1")
        if not (0 <= row and row + rowspan <= self.rows and 0 <= col and col + colspan <= self.cols):
            raise IndexError(f"cell (row={row}, col={col}, rowspan={rowspan}, colspan={colspan}) is outside the {self.rows}x{self.cols} grid")
        x, y = self._col_x[col], self._row_y[row]
        w = sum(self._col_w[col:col + colspan]) + self.wspace * (colspan - 1)
        h = sum(self._row_h[row:row + rowspan]) + self.hspace * (rowspan - 1)
        return x, y, w, h

    def subplot(self, row: int, col: int, rowspan: int = 1, colspan: int = 1, *, x_range: Point = (0, 1), y_range: Point = (0, 1), origin: Point | Literal["auto"] | None = "auto", margins: Point | Literal["auto"] | None = "auto", style: PlotStyle | None = None, extra_margins: Sequence[Number] = (0, 0, 0, 0)) -> Plot:
        """Create a :class:`Plot` occupying the given grid cell(s) and return it.

        ``row``/``col`` are zero-based. ``origin``/``margins`` are in the
        subplot's local coordinates (see :class:`Plot`).
        """
        x, y, w, h = self.cellBox(row, col, rowspan, colspan)
        cells = [(r, c) for r in range(row, row + rowspan) for c in range(col, col + colspan)]
        taken = [cell for cell in cells if cell in self._occupied]
        if taken:
            raise ValueError(f"grid cell(s) {taken} are already used by another subplot")
        plot = Plot(h, w, None, None, x_range, y_range, style=style if style is not None else self.style, extra_margins=extra_margins, executables=self.executables)
        plot.default_font = self.default_font
        plot.arrow_style = self.arrow_style
        plot._setLayout(origin, margins)  # re-run now that the figure's font is set
        slot = _SubplotSlot(plot, x, y, len(self._slots))
        for cell in cells:
            self._occupied[cell] = slot.index
        self._slots.append(slot)
        self.contents.append(slot)
        return plot

    def subplots(self, *, x_range: Point = (0, 1), y_range: Point = (0, 1), style: PlotStyle | None = None) -> list[list[Plot]]:
        """Create one subplot per grid cell and return them as ``axes[row][col]``."""
        return [[self.subplot(r, c, x_range=x_range, y_range=y_range, style=style) for c in range(self.cols)] for r in range(self.rows)]

    @property
    def plots(self) -> list[Plot]:
        """All subplots in creation order."""
        return [slot.plot for slot in self._slots]

    def _slotOf(self, plot: Plot) -> _SubplotSlot:
        for slot in self._slots:
            if slot.plot is plot:
                return slot
        raise KeyError("plot is not a subplot of this figure")

    def mapToFigure(self, plot: Plot, x: Number, y: Number, data: bool = True) -> Point:
        """Convert a point of ``plot`` to figure coordinates.

        With ``data=True`` (default) ``(x, y)`` are data coordinates; otherwise
        they are the subplot's local canvas coordinates.
        """
        slot = self._slotOf(plot)
        if data:
            (x, y) = plot.mapToCanvas(x, y)
        return (slot.x + x, slot.y + y)

    def _renderParts(self) -> tuple[list[str], list[str], set[str]]:
        defs, contents, fonts = list(self.defs), [], set(self.used_fonts)
        separator = '\n<!--svgflow:defs-end-->\n'
        for item in self.contents:
            if not isinstance(item, _SubplotSlot):
                contents.append(item)
                continue
            sub_defs, sub_contents, sub_fonts = item.plot._renderParts()
            block = '\n'.join(sub_defs) + separator + '\n'.join(sub_contents)
            block = uniquify_svg_ids(block, f'sp{item.index}')
            sub_defs_txt, sub_contents_txt = block.split(separator)
            if sub_defs_txt:
                defs.append(sub_defs_txt)
            contents.append(f'<g transform="translate({item.x:.4f} {item.y:.4f})">\n{sub_contents_txt}\n</g>')
            fonts |= sub_fonts
        return defs, contents, fonts

class FlowStyle:
    """Default appearance of nodes and edges in a :class:`Flow`.

    Every ``Flow`` drawing method falls back to these values for arguments
    left as ``None``, so a whole diagram can be restyled in one place::

        flow = Flow(400, 600, style=FlowStyle(node_color="aliceblue", edge_color="gray", arrow_style="stealth"))

    * ``node_shape``/``node_color``/``node_border``/``node_thickness``: node defaults.
    * ``text_size``/``text_color``/``text_style``: node label text.
    * ``edge_color``/``edge_thickness``: edge strokes.
    * ``edge_text_size``/``edge_text_color``: edge labels (``None`` = same as node text).
    * ``label_gap``: gap between an edge and its label, in units of the label font size.
    * ``arrow_style``/``arrow_size``: arrowheads (``None`` style = the canvas' :attr:`arrow_style`).
    * ``stub``/``corner_radius``: elbow-edge routing defaults.
    * ``self_loop_size``: default size of self-loops.
    """

    def __init__(self, *, node_shape: NodeShape = ('circle', 20), node_color: Color = 'none', node_border: Color = 'black', node_thickness: Number = 2, text_size: Number = 16, text_color: Color = 'black', text_style: str | None = None, edge_color: Color = 'black', edge_thickness: Number = 2, edge_text_size: Number | None = None, edge_text_color: Color | None = None, label_gap: Number = 0.4, arrow_style: ArrowStyle | None = None, arrow_size: Number = 1, stub: Number = 20, corner_radius: Number = 6, self_loop_size: Number = 100) -> None:
        self.node_shape = node_shape
        self.node_color = node_color
        self.node_border = node_border
        self.node_thickness = node_thickness
        self.text_size = text_size
        self.text_color = text_color
        self.text_style = text_style
        self.edge_color = edge_color
        self.edge_thickness = edge_thickness
        self.edge_text_size = edge_text_size
        self.edge_text_color = edge_text_color
        self.label_gap = label_gap
        self.arrow_style = arrow_style
        self.arrow_size = arrow_size
        self.stub = stub
        self.corner_radius = corner_radius
        self.self_loop_size = self_loop_size

    def copy(self, **overrides: Any) -> "FlowStyle":
        """Return a copy with some attributes replaced."""
        values = dict(self.__dict__)
        values.update(overrides)
        return FlowStyle(**values)

    def __repr__(self) -> str:
        args = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'FlowStyle({args})'


class Flow(Canvas):
    """Canvas with node and edge helpers for flow diagrams."""

    def __init__(self, height: Number, width: Number, *, style: FlowStyle | None = None, executables: ExecutablePaths | None = None) -> None:
        """Create an empty flow-diagram canvas whose defaults come from ``style``."""
        Canvas.__init__(self, height, width, executables=executables)
        self.style = style if style is not None else FlowStyle()
        self.nodes = dict()

    def _edgeDefaults(self, color: Color | None, thickness: Number | None, text_color: Color | None, text_size: Number | None, arrow_size: Number | None, arrow_style: ArrowStyle | None) -> tuple[Color, Number, Color, Number, Number, ArrowStyle | None]:
        # Resolves edge arguments left as None against self.style.
        s = self.style
        return (s.edge_color if color is None else color,
                s.edge_thickness if thickness is None else thickness,
                (s.edge_text_color or s.text_color) if text_color is None else text_color,
                (s.edge_text_size or s.text_size) if text_size is None else text_size,
                s.arrow_size if arrow_size is None else arrow_size,
                s.arrow_style if arrow_style is None else arrow_style)

    def _requireNode(self, *ids: str) -> None:
        for node_id in ids:
            if node_id not in self.nodes:
                raise KeyError(f'node {node_id} does not exist')

    def addNode(self, id: str, x: Number, y: Number, shape: NodeShape | None = None, label: Any | None = None, color: Color | None = None, border: Color | None = None, thickness: Number | None = None, opacity: Number = 1, text_color: Color | None = None, text_size: Number | None = None, text_style: str | None = None, latex: bool = False) -> None:
        """Add a named node using a circle, rectangle, ellipse, or parallelogram shape.

        Arguments left as ``None`` use the flow's :class:`FlowStyle`.
        """
        s = self.style
        shape = s.node_shape if shape is None else shape
        color = s.node_color if color is None else color
        border = s.node_border if border is None else border
        thickness = s.node_thickness if thickness is None else thickness
        text_color = s.text_color if text_color is None else text_color
        text_size = s.text_size if text_size is None else text_size
        text_style = s.text_style if text_style is None else text_style
        node_type = shape[0]
        if id not in self.nodes.keys():
            if node_type == 'circle':
                r = shape[1]
                self.nodes[id] = {'x' : x, 'y' : y, 'r' : r, 'label' : label, 'type': 'circle'}
                self.addCircle(x, y, r, color, border, thickness, opacity)
            elif node_type == 'rectangle':
                h, w = shape[1], shape[2]
                corner = shape[3] if len(shape) >= 4 else 0
                self.nodes[id] = {'x': x, 'y': y, 'h': h, 'w': w, 'rx': corner, 'label': label, 'type': 'rectangle'}
                self.addRectangle(h, w, x-w/2, y-h/2, color=color, border=border, thickness=thickness, opacity=opacity, corner_radius=corner)
            elif node_type == 'ellipse':
                a, b = shape[1], shape[2]
                self.nodes[id] = {'x': x, 'y': y, 'a': a, 'b': b, 'label': label, 'type': 'ellipse'}
                self.addEllipse(x, y, a, b, color=color, border=border, thickness=thickness, opacity=opacity)
            elif node_type in ('parallelogram', 'paralellogram'):  # old spelling kept for compatibility
                d1, d2, angle = shape[1], shape[2], shape[3] # d1 and d2 are the lengths of the diagonals
                angle *= np.pi/180
                a = np.sqrt((d1/2)**2 + (d2/2)**2 - d1 * d2 * np.cos(angle)/2)
                b = np.sqrt((d1/2)**2 + (d2/2)**2 + d1 * d2 * np.cos(angle)/2)
                w = np.abs(d1**2 - d2**2)/(4*b)
                h = np.sqrt(a**2 + w**2)
                u = np.sqrt(d1**2 - h**2)/2
                v = np.sqrt(d2**2 - h**2)/2
                p1 = (x + u, y - h/2)
                p2 = (x + v, y + h/2)
                p3 = (x - u, y + h/2)
                p4 = (x - v, y - h/2)
                self.nodes[id] = {'points': [p1, p2, p3, p4], 'x': x, 'y': y, 'label': label, 'type': 'parallelogram'}
                self.addPolygon(self.nodes[id]['points'], color=color, border=border, thickness=thickness, opacity=opacity)
            else:
                raise ValueError(f"invalid node shape {node_type}: supported node shapes are: circle, rectangle, ellipse, parallelogram")
            
            if label is not None:
                if latex:
                    self.addLaTeX(label, x, y, scale=(text_size)/16, color=text_color)
                else:
                    self.addText(label, x, y, color=text_color, size=text_size, style=text_style)
        else:
            raise KeyError(f'another node with id: {id} already exists')
    
    def _getIntersectionWithContainer(self, node_id: str, theta: Number) -> Point:
        # Point where the ray from the node centre at angle `theta` (degrees,
        # clockwise from +x) leaves the node's outline.
        theta = (theta+90) % (360) - 90
        if node_id not in self.nodes.keys():
            raise KeyError(f"node {node_id} does not exist")
        node = self.nodes[node_id]
        x, y = node['x'], node['y']
        ux, uy = np.cos(theta * np.pi / 180), np.sin(theta * np.pi / 180)

        if node['type'] == 'circle':
            r = node['r']
            x1, y1 = x + r * ux, y + r * uy
        elif node['type'] == 'rectangle':
            h, w = node['h'], node['w']
            # Distance along the ray to the first vertical / horizontal side.
            tx = (w / 2) / abs(ux) if abs(ux) > 1e-12 else np.inf
            ty = (h / 2) / abs(uy) if abs(uy) > 1e-12 else np.inf
            t = min(tx, ty)
            x1, y1 = x + t * ux, y + t * uy
            # Rounded corners: if the hit lies in a corner zone, intersect the corner arc instead.
            r = min(node.get('rx', 0), w / 2, h / 2)
            if r > 0:
                ix, iy = w / 2 - r, h / 2 - r
                dx, dy = x1 - x, y1 - y
                if abs(dx) > ix + 1e-9 and abs(dy) > iy + 1e-9:
                    ccx, ccy = x + np.sign(dx) * ix, y + np.sign(dy) * iy
                    fx, fy = x - ccx, y - ccy
                    b = fx * ux + fy * uy
                    t = -b + np.sqrt(max(b * b - (fx * fx + fy * fy - r * r), 0.0))
                    x1, y1 = x + t * ux, y + t * uy
        elif node['type'] == 'ellipse':
            # Polar radius of the ellipse in direction theta (not the parametric angle).
            a, b = node['a'], node['b']
            r = a * b / np.hypot(b * ux, a * uy)
            x1, y1 = x + r * ux, y + r * uy
        elif node['type'] == 'parallelogram':
            points = node['points']
            (x1, y1) = self._computeInteresctionWithConvexPolygon(x, y, theta, points)
        else:
            raise ValueError(f"invalid node shape {node['type']}: supported node shapes are: circle, rectangle, ellipse, parallelogram")
        return (x1, y1)
    
    def addEdge(self, node1: str, node2: str, label: Any | None = None, curvature: Number = 0, color: Color | None = None, thickness: Number | None = None, dashed: bool = False, directed: Directed = False, opacity: Number = 1, text_color: Color | None = None, text_size: Number | None = None, text_style: str | None = None, latex: bool = False, *, arrow_size: Number | None = None, arrow_style: ArrowStyle | None = None) -> None:
        """Connect two distinct nodes with a straight or curved edge.

        With ``curvature != 0`` the edge is a quadratic curve whose control
        point is offset ``curvature`` from the midpoint of the node centres;
        it is clipped exactly where the curve leaves each node.
        """
        self._requireNode(node1, node2)
        if node1 == node2:
            raise KeyError('can not add self edge using addEdge - use addSelfEdge instead')
        color, thickness, text_color, text_size, arrow_size, arrow_style = self._edgeDefaults(color, thickness, text_color, text_size, arrow_size, arrow_style)
        gap = self.style.label_gap

        (x1, y1) = (self.nodes[node1]['x'], self.nodes[node1]['y'])
        (x2, y2) = (self.nodes[node2]['x'], self.nodes[node2]['y'])
        if curvature == 0:
            theta = self._getRot(x1, y1, x2, y2)
            (a1, b1) = self._getIntersectionWithContainer(node1, theta)
            (a2, b2) = self._getIntersectionWithContainer(node2, 180 + theta)
            self.addLine(a1, b1, a2, b2, color, thickness, dashed, directed, opacity, label, text_color, text_size, text_style, arrow_size, latex, arrow_style=arrow_style, label_gap=gap)
        else:
            # The curve leaves each centre heading straight for the control point,
            # so clip along those directions; this works for any orientation.
            (cx, cy) = self._getControlPoint(x1, y1, x2, y2, curvature)
            (a1, b1) = self._getIntersectionWithContainer(node1, self._getRot(x1, y1, cx, cy))
            (a2, b2) = self._getIntersectionWithContainer(node2, self._getRot(x2, y2, cx, cy))
            self._strokeSegments([[(a1, b1), (cx, cy), (a2, b2)]], color, thickness, False, 'none', opacity, directed, dashed, arrow_size, arrow_style)
            if label is not None:
                # Signed offset of the control point from the clipped chord, in
                # the same convention addCurvedLine uses.
                nx, ny = self._perpUnit(a1, b1, a2, b2)
                offset = (cx - (a1 + a2) / 2) * nx + (cy - (b1 + b2) / 2) * ny
                self._curvedLabel(a1, b1, a2, b2, offset, label, text_color, text_size, text_style, latex, gap)

    def addSelfEdge(self, node: str, theta1: Number = 60, theta2: Number = 120, curvature: Number | None = None, label: Any | None = None, color: Color | None = None, thickness: Number | None = None, dashed: bool = False, directed: Directed = False, opacity: Number = 1, text_color: Color | None = None, text_size: Number | None = None, text_style: str | None = None, arrow_size: Number | None = None, latex: bool = False, *, arrow_style: ArrowStyle | None = None) -> None:
        """Add a self-loop leaving ``node`` at angle ``theta1`` and returning at ``theta2``.

        Angles are in degrees, clockwise from +x (so 90 is straight down). The
        loop always bulges *outward*, leaving and re-entering perpendicular-ish
        to the outline; ``curvature`` sets its size (the apex lies about
        ``curvature / 2`` beyond the attachment points; the sign is ignored).
        The label is placed just outside the loop's apex.
        """
        self._requireNode(node)
        color, thickness, text_color, text_size, arrow_size, arrow_style = self._edgeDefaults(color, thickness, text_color, text_size, arrow_size, arrow_style)
        size = abs(self.style.self_loop_size if curvature is None else curvature)

        p1 = np.array(self._getIntersectionWithContainer(node, theta1), dtype=float)
        p2 = np.array(self._getIntersectionWithContainer(node, theta2), dtype=float)
        u1 = np.array([np.cos(np.deg2rad(theta1)), np.sin(np.deg2rad(theta1))])
        u2 = np.array([np.cos(np.deg2rad(theta2)), np.sin(np.deg2rad(theta2))])
        bisector = u1 + u2
        spread = float(np.hypot(*bisector))
        if spread < 1e-6:  # attachment points on opposite sides
            mid = np.deg2rad((theta1 + theta2) / 2)
            out = np.array([np.cos(mid), np.sin(mid)])
        else:
            out = bisector / spread
        # Cubic loop with handles along the outward rays; its apex lies
        # 0.75 * L * spread / 2 beyond the chord midpoint.
        L = size / (0.75 * max(spread, 0.5))
        c1, c2 = p1 + L * u1, p2 + L * u2
        self._strokeSegments([[tuple(p1), tuple(c1), tuple(c2), tuple(p2)]], color, thickness, False, 'none', opacity, directed, dashed, arrow_size, arrow_style)

        if label is not None:
            apex = 0.125 * p1 + 0.375 * c1 + 0.375 * c2 + 0.125 * p2
            lx, ly = apex + out * (text_size * self.style.label_gap + thickness / 2)
            if abs(out[1]) >= abs(out[0]):
                anchor = 'middle'
                baseline, latex_baseline = ('auto', 'text-top') if out[1] < 0 else ('hanging', 'hanging')
            else:
                anchor = 'start' if out[0] > 0 else 'end'
                baseline = latex_baseline = 'middle'
            if latex:
                self.addLaTeX(label, lx, ly, scale=text_size / 16, baseline=latex_baseline, anchor=anchor, color=text_color)
            else:
                self.addText(label, lx, ly, text_color, baseline=baseline, anchor=anchor, size=text_size, style=text_style)

    # ------------------------------------------------------------------ #
    # Elbow (orthogonal) edges
    # ------------------------------------------------------------------ #

    # Outward unit direction of each port in SVG coordinates (y grows downward).
    _PORT_DIRS = {'E': (1, 0), 'S': (0, 1), 'W': (-1, 0), 'N': (0, -1)}
    _PORT_ANGLES = {'E': 0, 'S': 90, 'W': 180, 'N': 270}

    def getPort(self, node: str, port: Port) -> Point:
        """Return the boundary point of ``node`` on side ``port`` (N/S/E/W)."""
        if node not in self.nodes:
            raise KeyError(f'node {node} does not exist')
        port = port.upper()
        if port not in self._PORT_ANGLES:
            raise ValueError(f"invalid port {port!r}: supported ports are N, S, E, W")
        (px, py) = self._getIntersectionWithContainer(node, self._PORT_ANGLES[port])
        return (float(px), float(py))

    def _autoPorts(self, node1: str, node2: str) -> tuple[str, str]:
        # Face the two nodes towards each other along the dominant axis.
        dx = self.nodes[node2]['x'] - self.nodes[node1]['x']
        dy = self.nodes[node2]['y'] - self.nodes[node1]['y']
        if abs(dx) >= abs(dy):
            return ('E', 'W') if dx >= 0 else ('W', 'E')
        return ('S', 'N') if dy >= 0 else ('N', 'S')

    @staticmethod
    def _portFacing(px: Number, py: Number, qx: Number, qy: Number) -> str:
        # The port on a node at p that best faces point q.
        dx, dy = qx - px, qy - py
        if abs(dx) >= abs(dy):
            return 'E' if dx >= 0 else 'W'
        return 'S' if dy >= 0 else 'N'

    @staticmethod
    def _routeOrthogonal(p1: Point, d1: tuple[int, int], p2: Point, d2: tuple[int, int], stub: Number) -> list[Point]:
        """Orthogonal route from port ``p1`` (facing ``d1``) to port ``p2`` (facing ``d2``).

        The route always leaves ``p1`` along ``d1`` and enters ``p2`` against ``d2``.
        """
        # Work in a frame where the first port is horizontal; transpose back at the end.
        transposed = d1[0] == 0
        if transposed:
            p1, p2 = (p1[1], p1[0]), (p2[1], p2[0])
            d1, d2 = (d1[1], d1[0]), (d2[1], d2[0])
        (x1, y1), (x2, y2) = p1, p2
        s1 = (x1 + stub * d1[0], y1)
        s2 = (x2 + stub * d2[0], y2 + stub * d2[1])

        if d2[1] == 0:  # both ports horizontal
            if d1[0] == -d2[0]:  # facing opposite ways, e.g. E -> W
                if (x2 - x1) * d1[0] >= 2 * stub:
                    # Target is ahead: Z-shape through the middle.
                    mx = (x1 + x2) / 2
                    pts = [p1, (mx, y1), (mx, y2), p2]
                else:
                    # Target is behind: step out, cross over at mid-height, step in.
                    my = (y1 + y2) / 2
                    pts = [p1, s1, (s1[0], my), (s2[0], my), s2, p2]
            else:  # same direction, e.g. E -> E: U-shape
                X = max(s1[0], s2[0]) if d1[0] > 0 else min(s1[0], s2[0])
                pts = [p1, (X, y1), (X, y2), p2]
        else:  # perpendicular, e.g. E -> N
            corner = (x2, y1)
            ahead_of_1 = (x2 - x1) * d1[0] >= stub
            ahead_of_2 = (y1 - y2) * d2[1] >= stub
            if ahead_of_1 and ahead_of_2:
                pts = [p1, corner, p2]  # simple L
            elif ahead_of_1:
                # Go part-way, turn, approach the target port from its side.
                mx = (x1 + x2) / 2 if (x2 - x1) * d1[0] > 0 else s1[0]
                pts = [p1, (mx, y1), (mx, s2[1]), s2, p2]
            else:
                pts = [p1, s1, (s1[0], s2[1]), s2, p2]

        if transposed:
            pts = [(b, a) for (a, b) in pts]
        return Flow._simplifyPath(pts)

    @staticmethod
    def _simplifyPath(points: Sequence[Point], eps: float = 1e-6) -> list[Point]:
        # Drop repeated points and interior points on a straight line.
        out: list[Point] = []
        for p in points:
            p = (float(p[0]), float(p[1]))
            if out and abs(out[-1][0] - p[0]) < eps and abs(out[-1][1] - p[1]) < eps:
                continue
            if len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if abs((bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)) < eps:
                    out[-1] = p
                    continue
            out.append(p)
        return out

    @staticmethod
    def _roundedPathData(points: Sequence[Point], radius: Number) -> str:
        # SVG path data for a polyline whose corners are rounded with quadratic curves.
        d = [f'M{points[0][0]:.4f} {points[0][1]:.4f}']
        for i in range(1, len(points) - 1):
            (ax, ay), (bx, by), (cx, cy) = points[i - 1], points[i], points[i + 1]
            l1 = np.hypot(bx - ax, by - ay)
            l2 = np.hypot(cx - bx, cy - by)
            r = min(radius, l1 / 2, l2 / 2)
            if r <= 0 or l1 == 0 or l2 == 0:
                d.append(f'L{bx:.4f} {by:.4f}')
                continue
            sx, sy = bx - (bx - ax) / l1 * r, by - (by - ay) / l1 * r
            ex, ey = bx + (cx - bx) / l2 * r, by + (cy - by) / l2 * r
            d.append(f'L{sx:.4f} {sy:.4f} Q{bx:.4f} {by:.4f} {ex:.4f} {ey:.4f}')
        d.append(f'L{points[-1][0]:.4f} {points[-1][1]:.4f}')
        return ' '.join(d)

    def addElbowEdge(self, node1: str, node2: str, from_port: Port | None = None, to_port: Port | None = None, waypoints: Sequence[Point] | None = None, label: Any | None = None, label_segment: int | Literal['longest'] = 'longest', stub: Number | None = None, corner_radius: Number | None = None, color: Color | None = None, thickness: Number | None = None, dashed: bool = False, directed: Directed = True, opacity: Number = 1, text_color: Color | None = None, text_size: Number | None = None, text_style: str | None = None, arrow_size: Number | None = None, latex: bool = False, *, arrow_style: ArrowStyle | None = None) -> list[Point]:
        """Connect two nodes with an orthogonal (elbow) edge.

        ``from_port``/``to_port`` are the sides of ``node1``/``node2`` the edge
        attaches to (``'N'``, ``'S'``, ``'E'``, ``'W'``); when omitted they are
        chosen so the nodes face each other. ``stub`` is the minimum distance
        the edge travels straight out of a port before bending, and
        ``corner_radius`` rounds the bends (0 gives sharp corners).

        ``waypoints`` overrides automatic routing: the edge goes from the
        port, through each waypoint in order, to the target port. Ports that
        are not given are then chosen to face the first/last waypoint.

        The label is placed on the longest segment by default, or on segment
        ``label_segment`` (an index into the routed segments).

        Returns the list of route points (useful for debugging/layout).
        """
        self._requireNode(node1, node2)
        if node1 == node2:
            raise KeyError('can not add self edge using addElbowEdge - use addSelfEdge instead')
        color, thickness, text_color, text_size, arrow_size, arrow_style = self._edgeDefaults(color, thickness, text_color, text_size, arrow_size, arrow_style)
        stub = self.style.stub if stub is None else stub
        corner_radius = self.style.corner_radius if corner_radius is None else corner_radius

        if waypoints:
            waypoints = [(float(a), float(b)) for (a, b) in waypoints]
            n1, n2 = self.nodes[node1], self.nodes[node2]
            from_port = (from_port or self._portFacing(n1['x'], n1['y'], *waypoints[0])).upper()
            to_port = (to_port or self._portFacing(n2['x'], n2['y'], *waypoints[-1])).upper()
            points = self._simplifyPath([self.getPort(node1, from_port), *waypoints, self.getPort(node2, to_port)])
        else:
            auto1, auto2 = self._autoPorts(node1, node2)
            from_port = (from_port or auto1).upper()
            to_port = (to_port or auto2).upper()
            p1, p2 = self.getPort(node1, from_port), self.getPort(node2, to_port)
            points = self._routeOrthogonal(p1, self._PORT_DIRS[from_port], p2, self._PORT_DIRS[to_port], stub)

        if len(points) < 2:
            return points

        start, end = self._arrowEnds(directed)
        stroke_points = list(points)
        heads: list[tuple[Number, Number, Number]] = []
        arrow = None
        if start or end:
            style, scale, tip_back, line_back = self._arrowMetrics(thickness, arrow_size, arrow_style)
            arrow = (style, scale, tip_back)
            if end:
                heads.append((*points[-1], self._tangentAngle(points[-2:], at_end=True)))
                stroke_points[-1] = self._trimBezier(stroke_points[-2:], line_back, at_end=True)[-1]
            if start:
                heads.append((*points[0], self._tangentAngle(points[:2], at_end=False)))
                stroke_points[0] = self._trimBezier(stroke_points[:2], line_back, at_end=False)[0]
        self._emitStroke(f'<path d="{self._roundedPathData(stroke_points, corner_radius)}"', color, thickness, opacity, dashed, 'none', heads, arrow)

        if label is not None:
            segments = list(zip(points[:-1], points[1:]))
            if label_segment == 'longest':
                idx = max(range(len(segments)), key=lambda i: np.hypot(segments[i][1][0] - segments[i][0][0], segments[i][1][1] - segments[i][0][1]))
            else:
                idx = int(label_segment)
            (ax, ay), (bx, by) = segments[idx]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            gap = text_size * self.style.label_gap
            if abs(ay - by) < 1e-9:  # horizontal segment: label above it
                if latex:
                    self.addLaTeX(label, mx, my - gap, scale=text_size / 16, baseline='text-top', anchor='middle', color=text_color)
                else:
                    self.addText(label, mx, my - gap, text_color, baseline='auto', anchor='middle', size=text_size, style=text_style)
            else:  # vertical segment: label to the right of it
                if latex:
                    self.addLaTeX(label, mx + gap, my, scale=text_size / 16, baseline='middle', anchor='start', color=text_color)
                else:
                    self.addText(label, mx + gap, my, text_color, baseline='middle', anchor='start', size=text_size, style=text_style)
        return points

    # img.addRectangle(50, 50, 50, 50, color="yellow", border="red", thickness=2, rotation=45, opacity=0.5)
    # img.addCircle(150, 150, 40, color="cyan", border="darkblue", thickness=2)
    # img.addLinePath([(50, 25), (150, 25), (175, 50), (175, 150), (150, 175), (50, 175), (25, 150), (25, 50)], color="orange", thickness=2, closed=True)
    
    # img.addLine(50, 50, 50, 150, color="blue", thickness=2)
    # img.addLine(50, 150, 150, 150, color="blue", thickness=2)
    # img.addLine(150, 150, 150, 50, color="blue", thickness=2)
    # img.addLine(150, 50, 50, 50, color="blue", thickness=2)
    # #img.addText("Hello World!", 100, 100, rotation=-45, anchor="middle", style="italic", size=50)
    # img.addLaTeX('\\frac{\\pi}{4}', 50, 50, scale=2, rot=45, baseline="middle", anchor="middle")
    # img.addLaTeX('\\frac{\\pi}{4}', 50, 50, scale=2, rot=0, baseline="middle", anchor="middle")
    # img.save("myImg.svg")
