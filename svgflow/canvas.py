# Author: Shobhit Bhatnagar
# email: shb.bhatnagar.96@gmail.com
# Requires: numpy and inkscape

"""Small SVG generation library for drawings, plots, and flow diagrams."""

from __future__ import annotations

import os
import re
import tempfile
import numpy as np
from .external_figures import ExecutablePaths, import_svg_from_file, tex2svg
from subprocess import run, CalledProcessError
from typing import Any, Iterable, Literal, Sequence, TypeAlias
from .text_metrics import DEFAULT_FONT_FAMILY, text_width

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

    def addText(self, text: Any, x: Number, y: Number, color: Color = "black", rotation: Number = 0, baseline: TextBaseline = "middle", anchor: TextAnchor = "middle", size: Number = 16, style: str | None = None, weight: str | Number | None = None) -> None:
        """Add a single SVG ``<text>`` element at ``(x, y)``."""
        # dominant-baseline: hanging, middle, text-top, auto
        # text-anchor: start, middle, end
        text_options = [f'font-size="{size}" ']
        if style is not None:
            text_options.append(f'font-style="{style}" ')
        if weight is not None:
            text_options.append(f'font-weight="{weight}"')
        text_options = ''.join(text_options)
        self.contents.append(f'<text fill="{color}" transform="translate({x:.4f} {y:.4f}) rotate({rotation:.4f})" dominant-baseline="{baseline}" text-anchor="{anchor}" {text_options}>{text}</text>')

    def addMultiLineText(self, lines: Sequence[Any], x: Number, y: Number, color: Color = "black", rotation: Number = 0, baseline: TextBaseline = "middle", anchor: TextAnchor = "middle", size: Number = 16, style: str | None = None, weight: str | Number | None = None, font_family: str | None = None, text_lengths: Sequence[Number] | None = None) -> None:
        """Add a multi-line SVG text block using ``tspan`` elements."""
        if not lines:
            return
        if text_lengths is not None and len(text_lengths) != len(lines):
            raise ValueError("text_lengths must contain one value per line")

        text_options = [f'font-size="{size}" ']
        if style is not None:
            text_options.append(f'font-style="{style}" ')
        if weight is not None:
            text_options.append(f'font-weight="{weight}"')
        if font_family is not None:
            text_options.append(f'font-family="{font_family}" ')
        text_options = ''.join(text_options)

        def length_options(index: int) -> str:
            if text_lengths is None:
                return ""
            return f' textLength="{text_lengths[index]:.4f}" lengthAdjust="spacingAndGlyphs"'

        svg_text = [f'<tspan dy="0"{length_options(0)}>{lines[0]}</tspan>']
        for i in range(1, len(lines)):
            svg_text.append(f'<tspan x="0" dy="1.2em"{length_options(i)}>{lines[i]}</tspan>')
        svg_text = '\n'.join(svg_text)
        self.contents.append(f'<text fill="{color}" transform="translate({x:.4f} {y:.4f}) rotate({rotation:.4f})" dominant-baseline="{baseline}" text-anchor="{anchor}" {text_options}>{svg_text}</text>')

    def addLine(self, x1: Number, y1: Number, x2: Number, y2: Number, color: Color = "black", thickness: Number = 1, dashed: bool = False, directed: bool = False, opacity: Number = 1, label: Any | None = None, text_color: Color = "black", text_size: Number = 16, text_style: str | None = None, arrow_size: Number = 1, latex: bool = False) -> Number:
        """Draw a straight line and optionally add an arrowhead and label."""
        if dashed:
            self.contents.append(f'<line x1="{x1:.4f}" y1="{y1:.4f}" x2="{x2:.4f}" y2="{y2:.4f}" stroke="{color}" stroke-width="{thickness}" stroke-opacity="{opacity}" stroke-dasharray="4"></line>')
        else:
            self.contents.append(f'<line x1="{x1:.4f}" y1="{y1:.4f}" x2="{x2:.4f}" y2="{y2:.4f}" stroke="{color}" stroke-width="{thickness}" stroke-opacity="{opacity}"></line>')
        
        theta = self._getRot(x1, y1, x2, y2)
        
        if directed:
            self._addArrow(x2, y2, theta, thickness, color, opacity, arrow_size)
        
        if label is not None:
            gap = 0 if latex else text_size * 0.4
            (x3, y3) = self._getControlPoint(x1, y1, x2, y2, gap)
            if theta < 90 and theta > -90:
                if latex:
                    self.addLaTeX(label, x3, y3, scale=(text_size)/16, rot=theta, baseline="text-top", anchor="middle", color=text_color)
                else:
                    self.addText(label, x3, y3, text_color, theta, "text-top", "middle", text_size, text_style)
            else:
                if latex:
                    self.addLaTeX(label, x3, y3, scale=(text_size)/16, rot=theta-180, baseline="text-top", anchor="middle", color=text_color)
                else:
                    self.addText(label, x3, y3, text_color, theta-180, "text-top", "middle", text_size, text_style)
        
        return theta
    
    def _addArrow(self, x: Number, y: Number, theta: Number, thickness: Number = 2, color: Color = 'black', opacity: Number = 1, size: Number = 1) -> None:
        if not self.is_arrow_def_included:
            self.defs.append(f'<path id="arrow" d="M-10 -5 Q-5 -0.5 0 0 Q-5 0.5 -10 5"/>')
            self.is_arrow_def_included = True
        thickness /= size
        self.contents.append(f'<use xlink:href="#arrow" transform="translate({x:.4f} {y:.4f}) rotate({theta:.4f}) scale({size:.4f} {size:.4f})" stroke="{color}" stroke-width="{thickness}" opacity="{opacity}" fill="none"/>')

    def addCurvedLine(self, x1: Number, y1: Number, x2: Number, y2: Number, curvature: Number, color: Color = "black", thickness: Number = 1, dashed: bool = False, directed: bool = False, opacity: Number = 1, label: Any | None = None, text_color: Color = "black", text_size: Number = 16, text_style: str | None = None, arrow_size: Number = 1, latex: bool = False) -> Point:
        """Draw a quadratic Bezier curve controlled by a signed curvature value."""
        (cx, cy) = self._getControlPoint(x1, y1, x2, y2, curvature)
        if curvature == 0:
            self.addLine(x1, y1, x2, y2, color, thickness, dashed, directed, opacity, label, text_color, text_size, text_style)
        else:
            if dashed:
                self.contents.append(f'<path d="M{x1:.4f} {y1:.4f} Q{cx:.4f} {cy:.4f} {x2:.4f} {y2:.4f}" stroke="{color}" stroke-width="{thickness}" stroke-opacity="{opacity}" stroke-dasharray="4" fill="none"/>')
            else:
                self.contents.append(f'<path d="M{x1:.4f} {y1:.4f} Q{cx:.4f} {cy:.4f} {x2:.4f} {y2:.4f}" stroke="{color}" stroke-width="{thickness}" stroke-opacity="{opacity}" fill="none"/>')
            if directed:
                theta = self._getRot(cx, cy, x2, y2)
                self._addArrow(x2, y2, theta, thickness, color, opacity, arrow_size)
            
            if label is not None:
                if curvature > 0:
                    gap = curvature/2 if latex else curvature/2 + text_size * 0.4
                    (x3, y3) = self._getControlPoint(x1, y1, x2, y2, gap)
                    baseline = "text-top"
                else:
                    gap = curvature/2 if latex else curvature/2 - text_size * 0.4
                    (x3, y3) = self._getControlPoint(x1, y1, x2, y2, gap)
                    baseline = "hanging"
                alpha = self._getRot(x1,y1,x2,y2)
                if alpha < 90 and alpha > -90:
                    if latex:
                        self.addLaTeX(label, x3, y3, scale=(text_size)/16, rot=alpha, baseline=baseline, anchor="middle", color=text_color)
                    else:
                        self.addText(label, x3, y3, text_color, alpha, baseline, "middle", text_size, text_style)
                else:
                    if latex:
                        self.addLaTeX(label, x3, y3, scale=(text_size)/16, rot=(alpha-180), baseline=baseline, anchor="middle", color=text_color)
                    else:
                        self.addText(label, x3, y3, text_color, alpha-180, baseline, "middle", text_size, text_style)
        return (cx, cy)

    def _getControlPoint(self, x1: Number, y1: Number, x2: Number, y2: Number, c: Number) -> Point:
        if x2 - x1 != 0:
            m = (y2 - y1) / (x2 - x1)
            cx = (x1 + x2) / 2 + c * m / np.sqrt(1 + m**2)
            cy = (y1 + y2) / 2 - c / np.sqrt(1 + m**2)
        else:
            cx = (x1 + x2) / 2 + c
            cy = (y1 + y2) / 2
        return (cx, cy)

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
        p_str = [f'{float(p[0]):.4f},{float(p[1]):4f}' for p in points]
        p_str = ' '.join(p_str)
        self.contents.append(f'<polygon points="{p_str}" fill="{color}" stroke="{border}" stroke-width="{thickness}" opacity="{opacity}"/>')
    
    def addLinePath(self, points: Sequence[Point], color: Color = "black", thickness: Number = 1, closed: bool = False, fill: Color = "none", opacity: Number = 1, directed: bool = False, dashed: bool = False, arrow_size: Number = 1) -> None:
        """Draw a polyline or closed polygonal path through ``points``."""
        n = len(points)
        if n < 2:
            raise ValueError("failed to add line path. number of points should be >= 2.")
        
        (x0, y0) = points[0]
        path_contents = [f'<path d="M {round(x0,4)} {round(y0,4)}']
        for i in range(1, n):
            (x, y) = points[i]
            path_contents.append(f'L{round(x,4)} {round(y,4)} ')

        if closed:
            path_contents.append('Z"')
        else:
            path_contents.append('"')

        if dashed:
            path_contents.append(' stroke-dasharray="4"')
        
        path_contents.append(f' stroke="{color}" stroke-width="{thickness}" fill="{fill}" opacity="{opacity}"/>')
        path = ''.join(path_contents)
        self.contents.append(path)

        if directed:
            (x1, y1) = points[-2]
            (x2, y2) = points[-1]
            theta = self._getRot(x1, y1, x2, y2)
            self._addArrow(x2, y2, theta, thickness, color, opacity, arrow_size)

    def addQuadraticPath(self, points: Sequence[Point], control_points: Sequence[Point], color: Color = 'black', thickness: Number = 1, closed: bool = False, fill: Color = 'none', opacity: Number = 1, directed: bool = False, dashed: bool = False, arrow_size: Number = 1) -> None:
        """Draw a path made of quadratic Bezier segments."""
        num_points = len(points)
        num_control_points = len(control_points)
        if num_points - 1 != num_control_points or num_points < 2:
            raise ValueError("failed to add quadratic path")
        (x0, y0) = points[0]
        path_contents = [f'<path d="M {x0} {y0}']
        for i in range(1, num_points):
            (x, y) = points[i]
            (cx, cy) = control_points[i-1]
            path_contents.append(f'Q{round(cx,4)} {round(cy,4)} {round(x,4)} {round(y,4)} ')
        if closed:
            path_contents.append('Z"')
        else:
            path_contents.append('"')
        
        if dashed:
            path_contents.append(' stroke-dasharray="4"')
        
        path_contents.append(f' stroke="{color}" stroke-width="{thickness}" fill="{fill}" opacity="{opacity}"/>')
        path = ''.join(path_contents)
        self.contents.append(path)

        if directed:
            theta = self._getRot(cx, cy, x, y)
            self._addArrow(x, y, theta, thickness, color, opacity, arrow_size)
    
    def addCubicPath(self, points: Sequence[Point], control_points_1: Sequence[Point], control_points_2: Sequence[Point], color: Color = 'black', thickness: Number = 1, closed: bool = False, fill: Color = 'none', opacity: Number = 1, directed: bool = False, dashed: bool = False, arrow_size: Number = 1) -> None:
        """Draw a path made of cubic Bezier segments."""
        num_points = len(points)
        num_control_points_1 = len(control_points_1)
        num_control_points_2 = len(control_points_2)

        if (num_points - 1 != num_control_points_1) or (num_points - 1 != num_control_points_2) \
            or num_control_points_1 != num_control_points_2 or num_points < 2:
            raise ValueError("failed to add cubic path")
        
        (x0, y0) = points[0]
        path_contents = [f'<path d="M {x0} {y0}']
        for i in range(1, num_points):
            (x, y) = points[i]
            (x1, y1) = control_points_1[i-1]
            (x2, y2) = control_points_2[i-1]
            path_contents.append(f'C{round(x1,4)} {round(y1,4)} {round(x2,4)} {round(y2,4)} {round(x,4)} {round(y,4)} ')
        if closed:
            path_contents.append('Z"')
        else:
            path_contents.append('"')
        
        if dashed:
            path_contents.append(' stroke-dasharray="4"')
        
        path_contents.append(f' stroke="{color}" stroke-width="{thickness}" fill="{fill}" opacity="{opacity}"/>')
        path = ''.join(path_contents)
        self.contents.append(path)

        if directed:
            theta = self._getRot(x2, y2, x, y)
            self._addArrow(x, y, theta, thickness, color, opacity, arrow_size)

    def addCurve(self, points: Sequence[Point], color: Color = 'black', thickness: Number = 1, closed: bool = False, fill: Color = 'none', opacity: Number = 1, directed: bool = False, dashed: bool = False, arrow_size: Number = 1) -> None:
        """Fit and draw a smooth cubic Bezier curve through the supplied points."""
        curve_points = list(points)
        a, b = self._fitBezierCurve(curve_points, closed=closed)
        if closed:
            self.addCubicPath(curve_points + [curve_points[0]], a, b, color=color, thickness=thickness, directed=directed, fill=fill, opacity=opacity, dashed=dashed, arrow_size=arrow_size)
        else:
            self.addCubicPath(curve_points, a, b, color=color, thickness=thickness, directed=directed, fill=fill, opacity=opacity, dashed=dashed, arrow_size=arrow_size)
    
    def addCircularArc(self, x: Number, y: Number, r: Number, theta1: Number, theta2: Number, color: Color = 'black', thickness: Number = 1, fill: Color = 'none', opacity: Number = 1, directed: bool = False, dashed: bool = False, arrow_size: Number = 1) -> None:
        """Draw a circular SVG arc between two angles in degrees."""
        x1 = x + r * np.cos(theta1 * np.pi / 180)
        y1 = y + r * np.sin(theta1 * np.pi / 180)
        x2 = x + r * np.cos(theta2 * np.pi / 180)
        y2 = y + r * np.sin(theta2 * np.pi / 180)
        largeArcFlag = 1 if ((theta2 - theta1 > 180) or (theta2 - theta1 < -180)) else 0
        if theta1 > theta2:
            sweepFlag = 0
            sgn = -1
        else:
            sweepFlag = 1
            sgn = 1
        dash_array = 'stroke-dasharray="4"' if dashed else ''
        self.contents.append(f'<path d="M {x1:.4f} {y1:.4f} A {r:.4f} {r:.4f} 0 {largeArcFlag} {sweepFlag} {x2:.4f} {y2:.4f}" stroke="{color}" stroke-width="{thickness}" fill="{fill}" opacity="{opacity}" {dash_array}/>')
        if directed:
            self._addArrow(x2, y2, 90 * sgn + theta2, thickness, color, opacity, arrow_size)
    
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
        if grad_id not in self.gradients:
            raise KeyError(f'no gradient defined with id: {grad_id}')
        return f'url(#grad_{grad_id})'

    def save(self, filename: str | os.PathLike[str]) -> None:
        """Write the accumulated SVG markup to ``filename``."""
        file_contents = [f'<svg width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg">']
        if len(self.defs) > 0:
            file_contents.append('<defs>')
            file_contents.extend(self.defs)
            file_contents.append('</defs>')
        file_contents.extend(self.contents)
        file_contents.append('</svg>')
        filetxt = '\n'.join(file_contents)
        with open(filename, 'w', encoding="utf-8") as f:
            f.write(filetxt)
    
    def _findAttribute(self, svg_text: str, attribute: str) -> str:
        result = re.search(rf'{attribute}=(["\'])(.+?)\1', svg_text)
        return result.group(2)
    
    def _replaceAttribute(self, svg_text: str, attribute: str, new_value: Any) -> str:
        pattern = rf'({attribute}=["\'])(.+?)(["\'])'
        replacement = r"\1" + str(new_value) + r"\3"
        new_svg_text = re.sub(pattern, replacement, svg_text)
        return new_svg_text

    def export(self, filename: str | os.PathLike[str], export_type: ExportType = 'png', dpi: int = 200) -> None:
        """Export the canvas to PNG or PDF via Inkscape."""
        if export_type not in {'png', 'pdf'}:
            raise ValueError(f'unexpected export type: {export_type}. supported export types are: png, pdf')

        with tempfile.TemporaryDirectory() as temp_dir:
            svg_path = os.path.join(temp_dir, 'tmp.svg')
            self.save(svg_path)
            try:
                if export_type == 'png':
                    run([self.executables.inkscape, svg_path, f'--export-type={export_type}', f'--export-filename={filename}', f'--export-dpi={dpi}'], check=True, capture_output=True)
                elif export_type == 'pdf':
                    run([self.executables.inkscape, svg_path, f'--export-type={export_type}', f'--export-filename={filename}'], check=True, capture_output=True)
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
        if sub_fig_id in self.sub_figs:
            raise KeyError(f"sub figure id {sub_fig_id} already exists")
        sub_fig_id = str(sub_fig_id)
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
        # A helper function that computes the control points of a bezier curve passing through the given list of points.
        n = len(points)-1
        x = np.array([i for (i,_) in points])
        y = np.array([j for (_,j) in points])
        A = 4 * np.identity(n)
        np.fill_diagonal(A[1:], 1)
        np.fill_diagonal(A[:, 1:], 1)
        A[0, 0] = 2
        A[n-1, n-1] = 7
        A[n-1, n-2] = 2
        b = 4 * np.ones(n)
        b[0] = 1
        b[n-1] = 8
        c = 2 * np.ones(n)
        c[n-1] = 1
        X = x[:n] * b + x[1:] * c
        Y = y[:n] * b + y[1:] * c
        ax = np.linalg.solve(A, X)
        ay = np.linalg.solve(A, Y)
        bx = np.zeros(n)
        by = np.zeros(n)
        bx[:n-1] = 2 * x[1:n] - ax[1:]
        by[:n-1] = 2 * y[1:n] - ay[1:]
        bx[n-1] = (ax[n-1] + x[n]) / 2
        by[n-1] = (ay[n-1] + y[n]) / 2

        if closed == True:
            gx = -bx[n-1] + x[n]
            gy = -by[n-1] + y[n]
            hx = -x[0] + ax[0]
            hy = -y[0] + ay[0]

            a1_x = gx + x[n]
            a1_y = gy + y[n]
            b1_x = x[0] - hx
            b1_y = y[0] - hy
            ax = np.append(ax, a1_x)
            ay = np.append(ay, a1_y)
            bx = np.append(bx, b1_x)
            by = np.append(by, b1_y)

        a = list(zip(ax, ay))
        b = list(zip(bx, by))
        return (a, b)

class Plot(Canvas):
    """Canvas with helpers for drawing simple 2D plots."""

    def __init__(self, height: Number, width: Number, origin: Point | None = None, margins: Point | None = None, x_range: Point = (0, 1), y_range: Point = (0, 1), *, executables: ExecutablePaths | None = None) -> None:
        """Create a plotting canvas with data-to-canvas coordinate mapping."""
        Canvas.__init__(self, height, width, executables=executables)
        if origin is None:
            self.O_x = 0.15 * width
            self.O_y = 0.85 * height
        else:
            (self.O_x, self.O_y) = origin # this is where the bottom left corner of our plot will be positioned on the canvas
        if margins is None:
            self.m_x = 0.1 * width
            self.m_y = 0.1 * height
        else:
            (self.m_x, self.m_y) = margins # this is how much space will be left out on the right hand side and on the top
        (self._x, self.x_) = x_range # the values on the x axis will range between [_x, x_]
        (self._y, self.y_) = y_range # the values on the y axis will range between [_y, y_]
        self.is_cross_def_included = False
        self.is_square_def_included = False
        self.legend_items = []

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

    def addTicksX(self, labels: Iterable[tuple[Number, Any]], color: Color = "black", notch_thickness: Number = 2, notch_length: Number = 10, rotation: Number = 0, text_anchor: TextAnchor = "middle", text_size: Number = 16, grid: bool = True) -> None:
        """Add x-axis tick labels and optional vertical grid lines."""
        for x, label in labels:
            (x_tick, y_tick) = self.mapToCanvas(x, self._y)
            self.addText(label, x = x_tick, y = y_tick + notch_length, color = color, rotation = rotation, baseline = "hanging", anchor = text_anchor, size = text_size)
            if x != self._x:
                self.addLine(x1 = x_tick, x2 = x_tick, y1 = y_tick - notch_length / 2, y2 = y_tick + notch_length / 2, color = color, thickness = notch_thickness)
                if grid:
                    self.addLine(x1 = x_tick, x2 = x_tick, y1 = self.O_y, y2 = self.m_y, color = "gray", thickness = 1, dashed = True)

    def addTicksY(self, labels: Iterable[tuple[Number, Any]], color: Color = "black", notch_thickness: Number = 2, notch_length: Number = 10, rotation: Number = 0, text_baseline: TextBaseline = "middle", text_size: Number = 16, grid: bool = True) -> None:
        """Add y-axis tick labels and optional horizontal grid lines."""
        for y, label in labels:
            (x_tick, y_tick) = self.mapToCanvas(self._x, y)
            self.addText(label, y = y_tick, x = x_tick - notch_length, color = color, rotation = rotation, baseline = text_baseline, anchor = "end", size = text_size)
            if y != self._y:
                self.addLine(y1 = y_tick, y2 = y_tick, x1 = x_tick - notch_length / 2, x2 = x_tick + notch_length / 2, color = color, thickness = notch_thickness)
                if grid:
                    self.addLine(y1 = y_tick, y2 = y_tick, x1 = self.O_x, x2 = self.width - self.m_x, color = "gray", thickness = 1, dashed = True)

    def addBar(self, x: Number, y: Number, bar_width: Number, _y: Number = 0, bar_color: Color = "orange", opacity: Number = 1) -> None:
        """Draw a single vertical bar from ``_y`` to ``y``."""
        (x1, y1) = self.mapToCanvas(x, _y)
        (_, y2) = self.mapToCanvas(x, y)
        self.addRectangle(height=y1-y2, width=bar_width, x=(x1-bar_width/2), y=y2, color=bar_color, border='none', opacity=opacity)

    def addAxisLabels(self, xlabel: str | None = None, ylabel: str | None = None, xsize: Number = 16, ysize: Number = 16, color: Color = "black", xpad: Number | None = None, ypad: Number | None = None, xrot: Number = 0, yrot: Number = 0, xlatex: bool = False, ylatex: bool = False) -> None:
        """Add optional x- and y-axis labels."""
        if xpad is None:
            xpad = (self.height - self.O_y)/2
        if ypad is None:
            ypad = self.O_x/2
        
        if xlabel is not None:
            x_mid, y_axis = self.mapToCanvas((self._x + self.x_)/2, self._y)
            y = y_axis + xpad
            if xlatex:
                self.addLaTeX(xlabel, x_mid, y, baseline="hanging", anchor="middle", scale=(xsize/16), rot=xrot)
            else:
                self.addText(xlabel, x_mid, y, color=color, rotation=xrot, baseline="hanging", anchor="middle", size=xsize)

        if ylabel is not None:
            x_axis, y_mid = self.mapToCanvas(self._x, (self._y + self.y_)/2)
            x = x_axis - ypad
            if ylatex:
                self.addLaTeX(ylabel, x, y_mid, baseline="middle", anchor="middle", scale=(ysize/16), rot=(yrot-90))
            else:
                self.addText(ylabel, x, y_mid, color=color, rotation=(yrot-90), baseline="middle", anchor="middle", size=ysize)

    def addTitle(self, title: str, size: Number = 18, color: Color = "black", pad: Number = 18, latex: bool = False) -> None:
        """Add a title above the plot area."""
        x_mid, y_top = self.mapToCanvas((self._x + self.x_)/2, self.y_)
        y = y_top - pad
        if latex:
            self.addLaTeX(title, x_mid, y, scale=size/16)
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
        
    def addLegend(self, anchor: LegendAnchor | None = 'NE', text_size: Number = 16, text_color: Color = 'black', marker_scale: Number = 1, box_color: Color = 'yellow', box_border_color: Color = 'red', box_opacity: Number = 0.5, position: Point | None = None) -> None:
        """Draw a legend from the labels registered by plot methods."""
        sorted(self.legend_items, key=lambda x: x[1]['type'])
        lines = [x[0] for x in self.legend_items]

        line_widths = [text_width(line, text_size) for line in lines]
        legend_width = max(line_widths) + 20 * marker_scale
        legend_height = len(lines) * 1.2 * text_size
        
        if (anchor == None) or (position is not None):
            (x, y) = position
        else:
            x, y = self._computeLegendPosition(legend_width, legend_height, anchor)
        x_text = x + 15 * marker_scale
        y_text = y + 0.6 * text_size
        self.addRectangle(legend_height, legend_width, x - 5 * marker_scale, y, color=box_color, border=box_border_color, thickness=2, opacity=box_opacity, corner_radius=10)
        
        self.addMultiLineText(
            lines,
            x_text,
            y_text,
            text_color,
            size=text_size,
            anchor="start",
            font_family=DEFAULT_FONT_FAMILY,
            text_lengths=line_widths,
        )
        for i, (_, plot_info) in enumerate(self.legend_items):
            y_item = y_text + i * 1.2 * text_size
            if plot_info['type'] == 'plot':
                x1 = x + 10 * marker_scale
                self.addLine(x, y_item, x1, y_item, color=plot_info['color'], thickness=plot_info['thickness'], dashed=plot_info['dashed'], opacity=plot_info['opacity'])
            elif (plot_info['type'] == 'scatter') or (plot_info['type']=='bar'):
                x1 = x + 5 * marker_scale
                self.putMarker(x1, y_item, marker_type=plot_info['marker_type'], size=marker_scale, color=plot_info['color'], on_canvas=False)
    
    def easyTicks(self, color: Color = 'black', ticks_per_unit: Number = 0.01, notch_thickness: Number = 2, notch_length: Number = 15, rot_x: Number = 0, rot_y: Number = 0, text_size: Number = 16, grid: bool = False) -> None:
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
            self.addTicksX(x_labels, color, notch_thickness, notch_length, rot_x, "middle", text_size, grid)
        if num_y_ticks > 0:
            y_ticks = np.linspace(self._y, self.y_, num=num_y_ticks)
            y_labels = [(y, f'{y:.2f}') for y in y_ticks]
            self.addTicksY(y_labels, color, notch_thickness, notch_length, rot_y, "middle", text_size, grid)
    
    def easyAxes(self, color: Color = 'black', thickness: Number = 2, directed: bool = True, ticks_per_unit: Number = 0.01, notch_length: Number = 15, rot_x: Number = 0, rot_y: Number = 0, text_size: Number = 16, grid: bool = False) -> None:
        """Draw axes and automatically chosen ticks."""
        self.addAxes(color, thickness, directed)
        self.easyTicks(color, ticks_per_unit, thickness, notch_length, rot_x, rot_y, text_size, grid)

class Flow(Canvas):
    """Canvas with node and edge helpers for flow diagrams."""

    def __init__(self, height: Number, width: Number, *, executables: ExecutablePaths | None = None) -> None:
        """Create an empty flow-diagram canvas."""
        Canvas.__init__(self, height, width, executables=executables)
        self.nodes = dict()
    
    def addNode(self, id: str, x: Number, y: Number, shape: NodeShape = ('circle', 20), label: Any | None = None, color: Color = "none", border: Color = "black", thickness: Number = 2, opacity: Number = 1, text_color: Color = "black", text_size: Number = 16, text_style: str | None = None, latex: bool = False) -> None:
        """Add a named node using a circle, rectangle, ellipse, or parallelogram shape."""
        node_type = shape[0]
        if id not in self.nodes.keys():
            if node_type == 'circle':
                r = shape[1]
                self.nodes[id] = {'x' : x, 'y' : y, 'r' : r, 'label' : label, 'type': 'circle'}
                self.addCircle(x, y, r, color, border, thickness, opacity)
            elif node_type == 'rectangle':
                h, w = shape[1], shape[2]
                corner = shape[3] if len(shape) >= 4 else 0
                self.nodes[id] = {'x': x, 'y': y, 'h': h, 'w': w, 'label': label, 'type': 'rectangle'}
                self.addRectangle(h, w, x-w/2, y-h/2, color=color, border=border, thickness=thickness, opacity=opacity, corner_radius=corner)
            elif node_type == 'ellipse':
                a, b = shape[1], shape[2]
                self.nodes[id] = {'x': x, 'y': y, 'a': a, 'b': b, 'label': label, 'type': 'ellipse'}
                self.addEllipse(x, y, a, b, color=color, border=border, thickness=thickness, opacity=opacity)
            elif node_type == 'paralellogram':
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
                self.nodes[id] = {'points': [p1, p2, p3, p4], 'x': x, 'y': y, 'label': label, 'type': 'paralellogram'}
                self.addPolygon(self.nodes[id]['points'], color=color, border=border, thickness=thickness, opacity=opacity)
            else:
                raise ValueError(f"invalid node shape {node_type}: supported node shapes are: circle, rectangle, ellipse, paralellogram")
            
            if label is not None:
                if latex:
                    self.addLaTeX(label, x, y, scale=(text_size)/16, color=text_color)
                else:
                    self.addText(label, x, y, color=text_color, size=text_size, style=text_style)
        else:
            raise KeyError(f'another node with id: {id} already exists')
    
    def _getIntersectionWithContainer(self, node_id: str, theta: Number) -> Point:
        theta = (theta+90) % (360) - 90
        if node_id not in self.nodes.keys():
            raise KeyError(f"node {node_id} does not exist")

        if self.nodes[node_id]['type'] == 'circle':
            x, y = self.nodes[node_id]['x'], self.nodes[node_id]['y']
            r = self.nodes[node_id]['r']
            x1 = x + r * np.cos(theta * np.pi / 180)
            y1 = y + r * np.sin(theta * np.pi / 180)
        elif self.nodes[node_id]['type'] == 'rectangle':
            x, y = self.nodes[node_id]['x'], self.nodes[node_id]['y']
            h, w = self.nodes[node_id]['h'], self.nodes[node_id]['w']
            phi = 180 * np.arctan(h / w) / np.pi
            if (theta >= -phi) and (theta <= phi):
                x1 = x + w/2
                y1 = y + (w/2) * np.tan(theta * np.pi / 180)
            elif (theta > phi) and (theta <= 180 - phi):
                y1 = y + h/2
                x1 = x + (h/2) / np.tan(theta * np.pi / 180)
            elif (theta > 180 - phi) and (theta <= 180 + phi):
                x1 = x - w/2
                y1 = y - (w/2) * np.tan(theta * np.pi / 180) 
            else:
                y1 = y - h/2
                x1 = x - (h/2) / np.tan(theta * np.pi / 180)
        elif self.nodes[node_id]['type'] == 'ellipse':
            x, y = self.nodes[node_id]['x'], self.nodes[node_id]['y']
            a, b = self.nodes[node_id]['a'], self.nodes[node_id]['b']
            x1 = x + a * np.cos(theta * np.pi / 180)
            y1 = y + b * np.sin(theta * np.pi / 180)
        elif self.nodes[node_id]['type'] == 'paralellogram':
            x, y = self.nodes[node_id]['x'], self.nodes[node_id]['y']
            points = self.nodes[node_id]['points']
            (x1, y1) = self._computeInteresctionWithConvexPolygon(x, y, theta, points)
        else:
            raise ValueError(f"invalid node shape {self.nodes[node_id]['type']}: supported node shapes are: circle, rectangle, ellipse, paralellogram")
        return (x1, y1)
    
    def addEdge(self, node1: str, node2: str, label: Any | None = None, curvature: Number = 0, color: Color = "black", thickness: Number = 2, dashed: bool = False, directed: bool = False, opacity: Number = 1, text_color: Color = "black", text_size: Number = 16, text_style: str | None = None, latex: bool = False) -> None:
        """Connect two distinct nodes with a straight or curved edge."""
        if node1 not in self.nodes.keys():
            raise KeyError(f'node {node1} does not exist')
        if node2 not in self.nodes.keys():
            raise KeyError(f'node {node2} does not exist')
        if node1 == node2:
            raise KeyError('can not add self edge using addEdge - use addSelfEdge instead')
        
        (x1, y1) = (self.nodes[node1]['x'], self.nodes[node1]['y'])
        (x2, y2) = (self.nodes[node2]['x'], self.nodes[node2]['y'])
        theta = self._getRot(x1, y1, x2, y2)
        if curvature == 0:
            (a1, b1) = self._getIntersectionWithContainer(node1, theta)
            (a2, b2) = self._getIntersectionWithContainer(node2, 180 + theta)
            self.addLine(a1, b1, a2, b2, color, thickness, dashed, directed, opacity, label, text_color, text_size, text_style, latex=latex)
        else:
            alpha = 180 * np.arctan(2 * curvature / np.sqrt((x1-x2)**2 + (y1-y2)**2)) / np.pi
            (a1, b1) = self._getIntersectionWithContainer(node1, theta - np.sign(x2-x1) * alpha)
            (a2, b2) = self._getIntersectionWithContainer(node2, 180 + theta + np.sign(x2-x1) * alpha)
            (cx, cy) = self._getControlPoint(x1, y1, x2, y2, curvature)
            _curvature = np.sign(curvature) * np.sqrt(((a1+a2)/2 - cx)**2 + ((b1+b2)/2 - cy)**2)
            self.addCurvedLine(a1, b1, a2, b2, _curvature, color, thickness, dashed, directed, opacity, label, text_color, text_size, text_style, latex=latex)
    
    def addSelfEdge(self, node: str, theta1: Number = 60, theta2: Number = 120, curvature: Number = 100, label: Any | None = None, color: Color = "black", thickness: Number = 2, dashed: bool = False, directed: bool = False, opacity: Number = 1, text_color: Color = "black", text_size: Number = 16, text_style: str | None = None) -> None:
        """Add a curved self-loop edge to a node."""
        if node not in self.nodes.keys():
            raise KeyError(f'node {node} does not exist')
        (x1, y1) = self._getIntersectionWithContainer(node, theta1)
        (x2, y2) = self._getIntersectionWithContainer(node, theta2)
        self.addCurvedLine(x1, y1, x2, y2, curvature, color, thickness, dashed, directed, opacity, label, text_color, text_size, text_style)

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
