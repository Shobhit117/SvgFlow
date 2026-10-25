"""Render explicitly marked Markdown examples in isolated temporary directories.

Run with --latex to include examples requiring pdflatex and Inkscape.
Only repository-authored snippets marked ``render: core`` or ``render: latex``
are executed. Figures use page-prefixed filenames to avoid example collisions.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/figures"


def main():
    """Execute marked snippets and copy their actual saved SVGs to the docs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latex", action="store_true")
    parser.add_argument("--page", help="Render only this repository-relative Markdown path")
    args = parser.parse_args()
    count = 0
    pages = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    for page in pages:
        if args.page and page != (ROOT / args.page).resolve():
            continue
        prefix = "readme" if page == ROOT / "README.md" else page.stem
        text = page.read_text(encoding="utf-8")
        for index, (kind, code) in enumerate(re.findall(
            r"<!-- render: (core|latex) -->\s*```python\n(.*?)```", text, re.S
        ), 1):
            if kind == "latex" and not args.latex:
                continue
            previous = Path.cwd()
            with tempfile.TemporaryDirectory(prefix="svgflow-docs-") as directory:
                work = Path(directory)
                (work / "docs/figures").mkdir(parents=True)
                # Supply the same reusable asset referenced by the import examples.
                shutil.copyfile(OUTPUT / "icon.svg", work / "icon.svg")
                shutil.copyfile(OUTPUT / "icon.svg", work / "docs/figures/icon.svg")
                try:
                    os.chdir(work)
                    exec(compile(code, f"{page}:example{index}", "exec"),
                         {"__name__": "__docs_example__"})
                    for svg in work.glob("*.svg"):
                        # The seeded icon is an input, unless the snippet saves it.
                        if svg.name == "icon.svg" and 'icon.save("icon.svg")' not in code:
                            continue
                        shutil.copyfile(svg, OUTPUT / f"{prefix}-{svg.name}")
                        count += 1
                finally:
                    os.chdir(previous)
    print(f"Rendered {count} SVGs directly from Markdown examples.")


if __name__ == "__main__":
    main()
