# Author: Shobhit Bhatnagar
# email: shb.bhatnagar.96@gmail.com
# LaTeX conversion requires pdflatex and one configured SVG backend.

"""Helpers for converting LaTeX and existing SVG files into embeddable SVG."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from subprocess import run, CalledProcessError
from typing import Literal

TEMPLATE = '''\\documentclass[border=5pt]{{standalone}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\begin{{document}}
$\\displaystyle {content}$
\\end{{document}}
'''

CACHE_DIR = '.tex2svg'
# BOX_RE = re.compile(r"BBOX:HT=(\d+\.?\d*)pt,DP=(\d+\.?\d*)pt,WD=(\d+\.?\d*)pt")
ID_TOKEN = r'[-A-Za-z_][-A-Za-z0-9_.:-]*'

Backend = Literal["inkscape", "dvisvgm", "pdf2svg"]


@dataclass(frozen=True)
class ExecutablePaths:
    """Immutable command names or paths for optional external programs.

    Each field defaults to its command name, resolved using the subprocess
    environment's PATH. Supply executable paths as strings or path-like objects;
    do not add shell quotes or command-line flags to them. Only programs needed
    by the requested operation are invoked. This object does not install or
    validate executables. Pass it to Canvas, Plot, Figure, Flow or tex2svg.
    """

    inkscape: str | PathLike[str] = "inkscape"
    pdflatex: str | PathLike[str] = "pdflatex"
    dvisvgm: str | PathLike[str] = "dvisvgm"
    pdf2svg: str | PathLike[str] = "pdf2svg"


def uniquify_svg_ids(svg: str, prefix: str | None = None) -> str:
    """Return markup with declared IDs and supported references prefixed.

    Rewrites id attributes, url(#id), href and xlink:href references, leaving
    undeclared targets unchanged. This is a regex-based helper, not a general
    XML/CSS rewriter: CSS selectors and external resources are not resolved.
    ``prefix=None`` produces the literal prefix ``None_``; callers should pass
    an explicit unique prefix when composing fragments.
    """
    # 1) Collect all ids declared as id="…"/id='…'
    id_decl_re = re.compile(rf'\bid=(["\'])({ID_TOKEN})\1')
    ids = [m.group(2) for m in id_decl_re.finditer(svg)]
    if not ids:
        return svg  # nothing to do

    # Map old -> new
    mapping = {old: f"{prefix}_{old}" for old in ids}

    # 2) Replace id="…"/id='…' with prefixed value, preserving quote style
    def repl_id(m: re.Match[str]) -> str:
        """Prefix a declared ID while preserving the original attribute quote style."""
        quote, old = m.group(1), m.group(2)
        return f'id={quote}{mapping.get(old, old)}{quote}'
    svg = id_decl_re.sub(repl_id, svg)

    # 3) Replace url(#…)
    url_ref_re = re.compile(rf'url\(#({ID_TOKEN})\)')
    svg = url_ref_re.sub(lambda m: f'url(#{mapping.get(m.group(1), m.group(1))})', svg)

    # 4) Replace xlink:href="#…"/href="#…" (both quote types)
    href_re = re.compile(rf'\b(xlink:href|href)=(["\'])#({ID_TOKEN})\2')
    def repl_href(m: re.Match[str]) -> str:
        """Prefix a supported local href target while preserving its attribute name."""
        attr, quote, old = m.group(1), m.group(2), m.group(3)
        return f'{attr}={quote}#{mapping.get(old, old)}{quote}'
    svg = href_re.sub(repl_href, svg)
    return svg

def tex2svg(latex_math: str, eq_num: int, backend: Backend = "inkscape", *, executables: ExecutablePaths | None = None) -> tuple[str, float, float]:
    """Render a LaTeX math expression to SVG contents and return ``(svg, width, height)``.

    ``latex_math`` is math source without dollar delimiters; the standalone
    template loads amsmath/amssymb and wraps it in display-style math. Requires
    pdflatex plus the selected inkscape/dvisvgm/pdf2svg backend, found on PATH
    or via ``executables``. Every call uses a fresh temporary directory.

    The returned fragment excludes the outer svg element and has IDs prefixed
    with ``eq{eq_num}``; use unique equation numbers when composing fragments.
    Width and height come from the converter's viewBox in SVG user units.
    Missing programs raise ``FileNotFoundError``; failed subprocesses or
    unexpected SVG structure raise ``RuntimeError``. An unsupported backend
    raises ``ValueError`` after LaTeX compilation.
    """
    commands = executables or ExecutablePaths()
    tex_source = TEMPLATE.format(content=latex_math)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tex = tmp / "tmp.tex"
        pdf = tmp / "tmp.pdf"
        svg = tmp / "tmp.svg"
        # log = tmp / "tmp.log"
        tex.write_text(tex_source)
        try:
            run([commands.pdflatex, tex.name], cwd=tmp, check=True, capture_output=True) # generate pdf output
        except CalledProcessError as e:
            raise RuntimeError(f"pdflatex failed: {e.stderr.decode(errors='ignore')}")
        
        if backend == 'dvisvgm':
            try:
                run([commands.dvisvgm, '--no-fonts', '--pdf', pdf.name, '-o', svg.name], cwd=tmp, check=True, capture_output=True) # convert the pdf to svg
            except CalledProcessError as e:
                raise RuntimeError(f"dvisvgm failed: {e.stderr.decode(errors='ignore')}")
        elif backend == 'pdf2svg':
            try:
                run([commands.pdf2svg, pdf.name, svg.name], cwd=tmp, check=True, capture_output=True)
            except CalledProcessError as e:
                raise RuntimeError(f"pdf2svg failed: {e.stderr.decode(errors='ignore')}")
        elif backend == 'inkscape':
            try:
                run([commands.inkscape, pdf.name, '--pdf-poppler', '--export-type=svg', '--export-plain-svg', f'--export-filename={svg.name}'], cwd=tmp, check=True, capture_output=True)
            except CalledProcessError as e:
                raise RuntimeError(f"inkscape failed: {e.stderr.decode(errors='ignore')}")
        else:
            raise ValueError(f"invalid pdf to svg conversion backend: {backend} -- supported backends are dvisvgm, pdf2svg, inkscape")
        
        svgtxt = svg.read_text(encoding="utf-8")
        vb = re.search(r'viewBox=(["\'])(.+?)\1', svgtxt)
        inner = re.search(r"<svg[^>]*>(.*)</svg>", svgtxt, re.S) # search for contents inside the svg tags
        if (not vb) or (not inner):
            raise RuntimeError(f"unexpected svg structure from {backend}")

        vb = [float(v) for v in vb.group(2).split()]
        inner = inner.group(1).strip()
        _, _, W, H = vb
        inner = uniquify_svg_ids(inner, f'eq{eq_num}')
        return inner, W, H

def import_svg_from_file(file_name: str | Path, fig_num: int | str) -> tuple[str, list[float]]:
    """Return ``(inner_markup, [min_x, min_y, width, height])`` from a UTF-8 SVG.

    The root must contain a whitespace-separated viewBox and an explicit svg
    closing tag. Internal IDs/references are prefixed with ``fig{fig_num}``.
    Missing structure raises ``RuntimeError``; file errors propagate. This
    extracts markup without sanitizing it or bundling external resources.
    Prefer Canvas.importSvgFromFile for direct placement on a canvas.
    """
    svg = Path(file_name)
    svgtext = svg.read_text(encoding="utf-8")
    vb = re.search(r'viewBox=(["\'])(.+?)\1', svgtext)
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svgtext, re.S) # search for contents inside the svg tags
    if (not vb) or (not inner):
        raise RuntimeError(f"unexpected svg structure in file: {svg}")
    
    vb = [float(v) for v in vb.group(2).split()]
    inner = inner.group(1).strip()
    inner = uniquify_svg_ids(inner, f'fig{fig_num}')
    return inner, vb
