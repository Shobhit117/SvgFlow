"""Generate the SvgFlow logo with SvgFlow itself.

Concept
-------
* The wordmark is drawn stroke-by-stroke as a geometric monoline typeface
  built only from SvgFlow primitives (circular arcs, line paths, circles).
* The "S" is shown as it would look in a vector editor: anchor points and a
  tangent handle reveal that it is made of Bezier geometry -> "Svg".
* The "o" is a flow-diagram node, and the last stroke of the "w" breaks out
  of the word as a directed edge -> "Flow".
* "Flow" is painted with a hand-computed colour ramp, sampled per stroke.

Run:  python docs/logo/make_logo.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from svgflow import Canvas  # noqa: E402

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
RAMP = [(0.00, (6, 182, 212)),    # cyan
        (0.40, (59, 130, 246)),   # blue
        (0.70, (139, 92, 246)),   # violet
        (1.00, (236, 72, 153))]   # pink


def ramp(t: float) -> str:
    """Sample the brand colour ramp at t in [0, 1] and return rgb(...)."""
    t = min(max(t, 0.0), 1.0)
    for (t0, c0), (t1, c1) in zip(RAMP[:-1], RAMP[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            r, g, b = (round(a + (b_ - a) * u) for a, b_ in zip(c0, c1))
            return f"rgb({r}, {g}, {b})"
    r, g, b = RAMP[-1][1]
    return f"rgb({r}, {g}, {b})"


# --------------------------------------------------------------------------
# Monoline letter construction kit
# --------------------------------------------------------------------------
class Pen:
    """Draws round-capped monoline strokes on a Canvas."""

    def __init__(self, canvas: Canvas, thickness: float) -> None:
        self.c = canvas
        self.t = thickness

    def dot(self, x, y, color, r=None):
        self.c.addCircle(x, y, self.t / 2 if r is None else r, color=color, border="none")

    def line(self, pts, color, caps=True, joints=True):
        self.c.addLinePath(pts, color=color, thickness=self.t)
        ends = [pts[0], pts[-1]] if caps else []
        mids = pts[1:-1] if joints else []
        for p in ends + mids:
            self.dot(*p, color)

    def arc(self, cx, cy, r, a1, a2, color, caps=(True, True), **kw):
        self.c.addCircularArc(cx, cy, r, a1, a2, color=color, thickness=self.t, **kw)
        for flag, a in zip(caps, (a1, a2)):
            if flag:
                self.dot(cx + r * np.cos(np.radians(a)), cy + r * np.sin(np.radians(a)), color)

    def ring(self, cx, cy, r, color):
        self.c.addCircle(cx, cy, r, color="none", border=color, thickness=self.t)


def anchor(c: Canvas, x, y, size, accent, fill="white"):
    """Square vector-editor anchor point."""
    c.addRectangle(size, size, x - size / 2, y - size / 2, color=fill, border=accent,
                   thickness=max(1.5, size / 5), corner_radius=size / 6)


def handle(c: Canvas, x, y, dx, dy, accent, knob=4.5, fill="white"):
    """Tangent handle through (x, y) with round knobs on both ends."""
    c.addLine(x - dx, y - dy, x + dx, y + dy, color=accent, thickness=1.6)
    for s in (-1, 1):
        c.addCircle(x + s * dx, y + s * dy, knob, color=fill, border=accent, thickness=1.6)


# --------------------------------------------------------------------------
# Wordmark
# --------------------------------------------------------------------------
def wordmark(c: Canvas, x0: float, y_base: float, scale: float = 1.0,
             ink: str = "rgb(15, 23, 42)", paper: str = "white",
             accent: str = "rgb(6, 182, 212)") -> tuple[float, float]:
    """Draw 'SvgFlow' starting at x0 with the baseline centre-line at y_base.

    Returns the x coordinate where the wordmark ends and where 'Flow' starts.
    """
    k = scale
    t = 14 * k
    pen = Pen(c, t)
    cap_h, x_h = 86 * k, 46 * k            # centre-line heights
    Yb, Yx, Yc = y_base, y_base - x_h, y_base - cap_h
    gap = 17 * k
    x = x0

    # ---- S : two stacked arcs, shown with its Bezier anatomy -------------
    r = cap_h / 4
    cx = x + r
    top_c, bot_c = Yc + r, Yb - r
    pen.arc(cx, top_c, r, -35, -270, ink, caps=(True, False))
    pen.arc(cx, bot_c, r, 270, 505, ink, caps=(False, True))
    # vector-editor overlay: anchors on the terminals and the inflection
    p_top = (cx + r * np.cos(np.radians(-35)), top_c + r * np.sin(np.radians(-35)))
    p_bot = (cx + r * np.cos(np.radians(505)), bot_c + r * np.sin(np.radians(505)))
    mid = (cx, Yc + 2 * r)
    handle(c, *mid, 22 * k, 0, accent, knob=4.2 * k, fill=paper)
    for p in (p_top, mid, p_bot):
        anchor(c, *p, 10 * k, accent, fill=paper)
    x += 2 * r + gap

    # ---- v ---------------------------------------------------------------
    w = 42 * k
    pen.line([(x, Yx), (x + w / 2, Yb), (x + w, Yx)], ink)
    x += w + gap

    # ---- g : bowl + stem + descender hook --------------------------------
    r = x_h / 2
    pen.ring(x + r, Yb - r, r, ink)
    stem_bot = Yb + 12 * k
    pen.line([(x + 2 * r, Yx), (x + 2 * r, stem_bot)], ink, caps=False)
    pen.dot(x + 2 * r, Yx, ink)
    pen.arc(x + r, stem_bot, r, 0, 155, ink, caps=(False, True))
    x += 2 * r + gap * 1.45

    # ---- Flow : colour ramp sampled along x ------------------------------
    flow_x0 = x
    flow_w = 215 * k

    def col(px):
        return ramp((px - flow_x0) / flow_w)

    # F
    fw = 44 * k
    pen.line([(x, Yb), (x, Yc)], col(x), caps=True)
    pen.line([(x, Yc), (x + fw, Yc)], col(x + fw / 2))
    pen.line([(x, Yx), (x + fw * 0.82, Yx)], col(x + fw / 2))
    x += fw + gap * 0.95

    # l
    pen.line([(x, Yc - 6 * k), (x, Yb)], col(x))
    x += gap * 1.15

    # o : a flow node (gradient ring + core)
    r = x_h / 2
    ocx, ocy = x + r, Yb - r
    o_id = f"o_ring_{len(c.gradients)}"
    c.defineLinearGradient(o_id, 0, 0, 1, 0, stop_colors=(col(x), col(x + 2 * r)))
    o_grad = c.getGradient(o_id)
    pen.ring(ocx, ocy, r, o_grad)
    c.addCircle(ocx, ocy, 5.5 * k, color=col(ocx), border="none")
    x += 2 * r + gap * 0.9

    # w : the last stroke escapes as a directed edge
    ww = 66 * k
    pts = [(x, Yx), (x + ww * 0.25, Yb), (x + ww * 0.5, Yx + 14 * k),
           (x + ww * 0.75, Yb), (x + ww, Yx)]
    for a, b in zip(pts[:-2], pts[1:-1]):
        pen.line([a, b], col((a[0] + b[0]) / 2))
    # final stroke continues past the x-height and ends in an arrowhead
    (ax, ay), (bx, by) = pts[-2], pts[-1]
    ext = 1.95
    tip = (ax + (bx - ax) * ext, ay + (by - ay) * ext)
    c.addLine(ax, ay, *tip, color=col(tip[0]), thickness=t, directed=True,
              arrow_style="stealth", arrow_size=0.62)
    pen.dot(ax, ay, col(ax))
    return tip[0] + t, flow_x0


# --------------------------------------------------------------------------
# Icon mark
# --------------------------------------------------------------------------
def icon(c: Canvas, x: float, y: float, size: float, grad_id: str = "tile") -> None:
    """Gradient tile with a white 'S' that flows from a node into an arrow."""
    if grad_id not in c.gradients:
        c.defineLinearGradient(grad_id, 0, 0, 1, 1, stop_points=(0, 0.45, 1),
                               stop_colors=(ramp(0), ramp(0.45), ramp(1)))
    c.addRectangle(size, size, x, y, color=c.getGradient(grad_id), border="none",
                   corner_radius=size * 0.23)

    k = size / 200
    t = 19 * k
    pen = Pen(c, t)
    r = 30 * k
    cx, cy = x + size / 2, y + size / 2
    top_c, bot_c = cy - r, cy + r
    # source node
    a1 = -30
    sx, sy = cx + r * np.cos(np.radians(a1)), top_c + r * np.sin(np.radians(a1))
    pen.arc(cx, top_c, r, a1, -270, "white", caps=(False, False))
    pen.arc(cx, bot_c, r, 270, 450, "white", caps=(False, False))
    # the S leaves the tile's centre as a directed flow edge
    c.addLine(cx + 0.5, bot_c + r, cx - 40 * k, bot_c + r, color="white", thickness=t,
              directed=True, arrow_style="stealth", arrow_size=0.5)
    c.addCircle(sx, sy, 13 * k, color="white", border="none")
    c.addCircle(sx, sy, 5.5 * k, color=ramp(0.3), border="none")
    # Bezier handle at the inflection point
    handle(c, cx, cy, 34 * k, 0, "white", knob=6 * k, fill=ramp(0.5))
    anchor(c, cx, cy, 14 * k, "white", fill=ramp(0.5))


# --------------------------------------------------------------------------
def build(out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    files = []

    # Measure the wordmark once on a scratch canvas to size the artboards.
    end, flow_x = wordmark(Canvas(10, 10), 275, 172)
    W, H = int(end + 40), 260
    tagline = "DRAW  \u00b7  PLOT  \u00b7  FLOW"

    # 1. Primary horizontal logo (light backgrounds, transparent)
    c = Canvas(H, W)
    icon(c, 30, 30, 200)
    wordmark(c, 275, 172)
    c.addText(tagline, flow_x - 6, 228, size=14, anchor="start", weight="bold",
              color="rgb(100, 116, 139)", font="sans")
    files.append(os.path.join(out_dir, "svgflow-logo.svg"))
    c.save(files[-1])

    # 2. Dark variant on a slate card
    d = Canvas(H, W)
    d.addRectangle(H, W, 0, 0, color="rgb(15, 23, 42)", border="none", corner_radius=28)
    # faint dot grid, like an editor canvas
    for gx in range(20, W - 10, 20):
        for gy in range(20, H - 10, 20):
            d.addCircle(gx, gy, 1.1, color="rgb(41, 53, 72)", border="none")
    icon(d, 30, 30, 200)
    wordmark(d, 275, 172, ink="rgb(241, 245, 249)", paper="rgb(15, 23, 42)",
             accent="rgb(34, 211, 238)")
    d.addText(tagline, flow_x - 6, 228, size=14, anchor="start", weight="bold",
              color="rgb(148, 163, 184)", font="sans")
    files.append(os.path.join(out_dir, "svgflow-logo-dark.svg"))
    d.save(files[-1])
    # 3. Wordmark only
    w_end, _ = wordmark(Canvas(10, 10), 30, 118)
    w = Canvas(170, int(w_end + 30))
    wordmark(w, 30, 118)
    files.append(os.path.join(out_dir, "svgflow-wordmark.svg"))
    w.save(files[-1])

    # 4. Square icon / favicon
    i = Canvas(256, 256)
    icon(i, 8, 8, 240)
    files.append(os.path.join(out_dir, "svgflow-icon.svg"))
    i.save(files[-1])
    return files


if __name__ == "__main__":
    for f in build(HERE):
        print("wrote", f)
