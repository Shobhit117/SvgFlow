"""Check links, fenced Python syntax, reference coverage, docstrings and SVGs."""
import argparse
import ast
from collections import Counter
import inspect
import re
import subprocess
import sys
from urllib.parse import unquote
import xml.etree.ElementTree as ET

import svgflow
from docs.tools.build_reference import GROUPS, ROOT, render_all


def anchors(text):
    """Collect explicit IDs and common GitHub-style heading anchors."""
    found = set(re.findall(r'<a\s+id="([^"]+)"', text))
    counts = Counter()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        index = counts[slug]
        counts[slug] += 1
        found.add(slug if index == 0 else f"{slug}-{index}")
    return found


def main():
    """Check static contracts, optionally rebuilding executable examples first."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-examples", action="store_true")
    args = parser.parse_args()
    if args.run_examples:
        for module in ["docs.examples.gallery", "docs.examples.recipes"]:
            subprocess.run([sys.executable, "-m", module], cwd=ROOT, check=True)
    errors = []
    pages = sorted((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]
    snippets = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        prose_only = re.sub(r"```.*?```", "", text, flags=re.S)
        for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", prose_only):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            filename, _, fragment = unquote(target).partition("#")
            dest = (page.parent / filename).resolve() if filename else page
            if not dest.is_file():
                errors.append(f"{page.relative_to(ROOT)}: missing link {target}")
            elif fragment and dest.suffix == ".md" and fragment not in anchors(dest.read_text(encoding="utf-8")):
                errors.append(f"{page.relative_to(ROOT)}: missing anchor {target}")
        for index, code in enumerate(re.findall(r"```python\n(.*?)```", text, re.S), 1):
            if page.parent.name == "api":
                continue  # These are signatures, not executable statements.
            try:
                compile(code, str(page) + f":block{index}", "exec")
                snippets += 1
            except SyntaxError as error:
                errors.append(f"{page.relative_to(ROOT)} block {index}: {error}")
    for relative, current in render_all().items():
        path = ROOT / relative
        if not path.is_file() or path.read_text(encoding="utf-8") != current:
            errors.append(f"Stale reference: {relative}; run build_reference")
    reference = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "docs/api").glob("*.md"))
    for name in svgflow.__all__:
        if f"## {name}\n" not in reference:
            errors.append(f"Missing exported symbol: {name}")
    for _, _, objects in GROUPS.values():
        for obj in objects:
            if inspect.isclass(obj):
                for name, member in obj.__dict__.items():
                    if not name.startswith("_") and (inspect.isfunction(member) or isinstance(member, (property, classmethod))):
                        if f"## {obj.__name__}.{name}\n" not in reference:
                            errors.append(f"Missing method: {obj.__name__}.{name}")
    for path in (ROOT / "svgflow").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(node):
                errors.append(f"Missing docstring: {path.name}:{getattr(node, 'lineno', 1)}")
    svgs = sorted((ROOT / "docs/figures").glob("*.svg"))
    for path in svgs:
        try:
            root = ET.parse(path).getroot()
            ids = [e.attrib["id"] for e in root.iter() if "id" in e.attrib]
            duplicates = [name for name, count in Counter(ids).items() if count > 1]
            if duplicates:
                errors.append(f"{path.name}: duplicate IDs {duplicates}")
            for element in root.iter():
                for key, value in element.attrib.items():
                    refs = re.findall(r"url\(#([^)]*)\)", value)
                    if key.endswith("href") and value.startswith("#"):
                        refs.append(value[1:])
                    for ref in refs:
                        if ref not in ids:
                            errors.append(f"{path.name}: unresolved reference {ref}")
                    if re.search(r"(?:^|[\s,(])(?:nan|[+-]?inf)(?:$|[\s,)])", value, re.I):
                        errors.append(f"{path.name}: nonfinite attribute {key}")
            if not root.attrib.get("viewBox"):
                errors.append(f"{path.name}: no viewBox")
        except ET.ParseError as error:
            errors.append(f"{path.name}: {error}")
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"Checked {len(pages)} Markdown pages, {snippets} Python snippets, {len(svgs)} SVGs, "
          "all exports/methods/docstrings, and current generated reference.")


if __name__ == "__main__":
    main()
