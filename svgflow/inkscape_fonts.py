"""Make registered (file-backed) fonts visible to Inkscape during export.

Inkscape ignores ``@font-face`` rules in SVG files and resolves fonts through
fontconfig. To render registered fonts faithfully we give each Inkscape run a
private fontconfig configuration that:

* adds a temporary folder holding copies of the registered font files;
* renames those fonts' family to their svgflow registry name at scan time
  (``<match target="scan">``), because the SVG refers to them by that name;
* includes the normal system/Inkscape configuration so every other font
  (and fallback) keeps working.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
import warnings
from contextlib import contextmanager
from typing import Iterable, Iterator
from xml.sax.saxutils import escape

from .text_metrics import FontSpec


def _fc_path(path: str) -> str:
    # fontconfig accepts forward slashes on every platform.
    return os.path.abspath(path).replace("\\", "/")


def find_base_fontconfig(inkscape: str | os.PathLike[str] = "inkscape") -> str | None:
    """Locate the fontconfig configuration Inkscape would normally use.

    Checks ``$FONTCONFIG_FILE``, ``$FONTCONFIG_PATH/fonts.conf``, the config
    bundled next to the Inkscape executable (Windows/macOS builds), and the
    usual system locations. Returns ``None`` if nothing is found.
    """
    candidates: list[str] = []
    if os.environ.get("FONTCONFIG_FILE"):
        candidates.append(os.environ["FONTCONFIG_FILE"])
    if os.environ.get("FONTCONFIG_PATH"):
        candidates.append(os.path.join(os.environ["FONTCONFIG_PATH"], "fonts.conf"))
    exe = shutil.which(str(inkscape)) or (str(inkscape) if os.path.isfile(str(inkscape)) else None)
    if exe:
        exe_dir = os.path.dirname(os.path.realpath(exe))
        candidates += [
            os.path.join(exe_dir, "..", "etc", "fonts", "fonts.conf"),               # Windows: <Inkscape>/bin/inkscape.exe
            os.path.join(exe_dir, "..", "Resources", "etc", "fonts", "fonts.conf"),  # macOS app bundle
        ]
    candidates += ["/etc/fonts/fonts.conf", "/usr/local/etc/fonts/fonts.conf", "/opt/homebrew/etc/fonts/fonts.conf"]
    for path in candidates:
        if os.path.isfile(path):
            return os.path.normpath(path)
    return None


def build_fontconfig(font_dir: str, cache_dir: str, faces: Iterable[tuple[str, str]], base_config: str | None) -> str:
    """Return a fontconfig XML document.

    ``faces`` holds ``(family, file_path)`` pairs: each file (which must live in
    ``font_dir`` and have a unique file name) is exposed under ``family``.
    """
    rules = []
    for family, path in faces:
        rules.append(
            '  <match target="scan">\n'
            f'    <test name="file" compare="contains"><string>{escape(os.path.basename(path))}</string></test>\n'
            f'    <edit name="family" mode="assign_replace" binding="same"><string>{escape(family)}</string></edit>\n'
            '  </match>'
        )
    include = f'  <include ignore_missing="yes">{escape(_fc_path(base_config))}</include>\n' if base_config else ''
    return (
        '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n<fontconfig>\n'
        f'  <dir>{escape(_fc_path(font_dir))}</dir>\n'
        f'  <cachedir>{escape(_fc_path(cache_dir))}</cachedir>\n'
        + '\n'.join(rules) + '\n'
        + include
        + '</fontconfig>\n'
    )


@contextmanager
def inkscape_font_env(fonts: Iterable[FontSpec], inkscape: str | os.PathLike[str] = "inkscape") -> Iterator[dict[str, str] | None]:
    """Context manager yielding an environment for running Inkscape.

    The environment exposes every file-backed face of ``fonts`` under its
    registry name. Yields ``None`` (use the inherited environment) when no
    font needs exposing or the base fontconfig setup cannot be found.
    """
    faces = [(spec.name, path) for spec in fonts for path in spec.file_faces().values()]
    if not faces:
        yield None
        return
    base = find_base_fontconfig(inkscape)
    if base is None:
        warnings.warn("could not locate Inkscape's fontconfig configuration; registered fonts may not render in exported files", stacklevel=3)
        yield None
        return
    with tempfile.TemporaryDirectory(prefix="svgflow_fonts_") as tmp:
        font_dir = os.path.join(tmp, "fonts")
        os.makedirs(font_dir)
        token = uuid.uuid4().hex[:8]
        copied = []
        for i, (family, path) in enumerate(faces):
            # Unique, non-overlapping names so the "contains" test can't cross-match.
            dst = os.path.join(font_dir, f"svgflow-{token}-{i:03d}-face{os.path.splitext(path)[1].lower()}")
            shutil.copyfile(path, dst)
            copied.append((family, dst))
        conf_path = os.path.join(tmp, "fonts.conf")
        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(build_fontconfig(font_dir, os.path.join(tmp, "cache"), copied, base))
        env = dict(os.environ)
        env["FONTCONFIG_FILE"] = conf_path
        yield env
