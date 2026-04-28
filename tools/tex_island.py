"""Compile a single TeX-island source into an SVG file.

A TeX island is a self-contained `standalone`-class TeX document — typically a
display equation or a TikZ figure — that becomes one SVG embedded into a post.

Pipeline: source string -> latex -> dvi -> dvisvgm (woff2 fonts) -> svg.
Output is content-addressed: identical TeX produces identical filename.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IslandResult:
    svg_path: Path        # absolute path to generated SVG
    rel_path: str         # path relative to the post directory (for href use)
    cache_hit: bool       # True if SVG already existed and was reused


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def compile_island(source: str, build_dir: Path, name_hint: str | None = None) -> IslandResult:
    """Compile `source` (a complete standalone TeX document) into an SVG.

    `build_dir` is where intermediates and the SVG land. It is created if missing.
    `name_hint` is an optional human-readable prefix; the content hash is always
    appended so two islands with the same hint don't collide.
    """
    build_dir.mkdir(parents=True, exist_ok=True)
    digest = _hash(source)
    stem = f"{name_hint}-{digest}" if name_hint else digest
    tex_path = build_dir / f"{stem}.tex"
    dvi_path = build_dir / f"{stem}.dvi"
    svg_path = build_dir / f"{stem}.svg"

    # Path relative to the post root (build_dir is <post>/tex/build), POSIX-style for URLs.
    post_dir = build_dir.parent.parent
    rel_url = str(svg_path.relative_to(post_dir)).replace("\\", "/")

    if svg_path.exists():
        return IslandResult(svg_path=svg_path, rel_path=rel_url, cache_hit=True)

    tex_path.write_text(source, encoding="utf-8")

    latex_cmd = ["latex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
    proc = subprocess.run(latex_cmd, cwd=build_dir, capture_output=True, text=True)
    if proc.returncode != 0 or not dvi_path.exists():
        log = (build_dir / f"{stem}.log").read_text(encoding="utf-8", errors="replace") if (build_dir / f"{stem}.log").exists() else proc.stdout
        raise RuntimeError(f"latex failed for island {stem}\n--- log tail ---\n{log[-1500:]}")

    dvisvgm_cmd = [
        "dvisvgm",
        "--font-format=woff2",
        "--bbox=papersize",
        f"--output={svg_path.name}",
        dvi_path.name,
    ]
    proc = subprocess.run(dvisvgm_cmd, cwd=build_dir, capture_output=True, text=True)
    if proc.returncode != 0 or not svg_path.exists():
        raise RuntimeError(f"dvisvgm failed for island {stem}\n{proc.stderr}")

    # Clean compile-time intermediates; keep .tex for traceability and .svg as output.
    for ext in (".aux", ".log", ".dvi"):
        p = build_dir / f"{stem}{ext}"
        if p.exists():
            p.unlink()

    return IslandResult(svg_path=svg_path, rel_path=rel_url, cache_hit=False)


def clean(build_dir: Path) -> int:
    """Remove all artifacts under build_dir. Returns count removed."""
    if not build_dir.exists():
        return 0
    n = sum(1 for _ in build_dir.iterdir())
    shutil.rmtree(build_dir)
    return n
