"""Opt-in examples needing Inkscape and/or TeX.

Run from any directory with SvgFlow installed:
    python docs/examples/optional_integrations.py export
    python docs/examples/optional_integrations.py latex --backend inkscape

No optional executable is invoked merely by importing this module.
"""
import argparse
from pathlib import Path

from svgflow import Canvas

OUTPUT = Path(__file__).resolve().parents[1] / "figures"


def main():
    """Run only the explicitly selected external integration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=["export", "latex"])
    parser.add_argument("--backend", choices=["inkscape", "dvisvgm", "pdf2svg"], default="inkscape")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    c = Canvas(180, 500)
    c.addRectangle(180, 500, 0, 0, color="white", border="none")
    if args.example == "latex":
        c.addLaTeX(r"e^{i\pi}+1=0", 250, 90, scale=2, color="navy", backend=args.backend)
        c.save(OUTPUT / "latex.svg")
    else:
        c.addText("SvgFlow export", 250, 90, size=26)
        c.save(OUTPUT / "export.svg")
        c.export(OUTPUT / "export.png", export_type="png", dpi=150)
        c.export(OUTPUT / "export.pdf", export_type="pdf")


if __name__ == "__main__":
    main()
