"""Compile a single TeX-island source into an SVG file.

A TeX island is a self-contained `standalone`-class TeX document — typically a
display equation or a TikZ figure — that becomes one SVG embedded into a post.

Pipeline: source string -> latex -> dvi -> dvisvgm (woff2 fonts) -> svg.
Output is content-addressed: identical TeX produces identical filename.

Compile is error-tolerant: when `latex` or `dvisvgm` fails AND a previous
successful SVG exists with the same `name_hint`, the prior render is returned
with `stale=True` and `error` set to the log tail. Mirrors the behavior of
the user's old `pdflatex + Zathura` loop, where a broken edit kept the last
good preview on screen.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IslandResult:
    svg_path: Path        # absolute path to the SVG that should be referenced
    rel_path: str         # path relative to the post directory (for href use)
    cache_hit: bool       # True if SVG already existed and was reused
    stale: bool = False   # True if compile failed and we returned a previous render
    error: str | None = None  # Compile log tail when stale; None on success


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _last_good_for(build_dir: Path, name_hint: str | None) -> Path | None:
    """Find the most recent successfully compiled SVG with the same name hint."""
    if not name_hint or not build_dir.exists():
        return None
    candidates = sorted(
        build_dir.glob(f"{name_hint}-*.svg"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _read_log_tail(log_path: Path, lines: int = 40) -> str:
    if not log_path.exists():
        return ""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


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
    log_path = build_dir / f"{stem}.log"

    # Path relative to the post root (build_dir is <post>/tex/build), POSIX-style for URLs.
    post_dir = build_dir.parent.parent

    def rel(p: Path) -> str:
        return str(p.relative_to(post_dir)).replace("\\", "/")

    # Cache hit on identical content.
    if svg_path.exists():
        return IslandResult(svg_path=svg_path, rel_path=rel(svg_path), cache_hit=True)

    tex_path.write_text(source, encoding="utf-8")

    latex_cmd = ["latex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
    proc = subprocess.run(latex_cmd, cwd=build_dir, capture_output=True, text=True)
    if proc.returncode != 0 or not dvi_path.exists():
        log = _read_log_tail(log_path) or proc.stdout
        last_good = _last_good_for(build_dir, name_hint)
        # Clean up the failed-compile intermediates so the next attempt is clean.
        for ext in (".aux", ".log", ".dvi"):
            p = build_dir / f"{stem}{ext}"
            if p.exists():
                p.unlink()
        if last_good:
            return IslandResult(
                svg_path=last_good,
                rel_path=rel(last_good),
                cache_hit=False,
                stale=True,
                error=log,
            )
        # No prior render to fall back on — synthesize a placeholder SVG so the
        # build still completes and the reader sees an honest error in place of
        # the figure.
        placeholder = _placeholder_svg(stem, log)
        svg_path.write_text(placeholder, encoding="utf-8")
        return IslandResult(
            svg_path=svg_path,
            rel_path=rel(svg_path),
            cache_hit=False,
            stale=True,
            error=log,
        )

    dvisvgm_cmd = [
        "dvisvgm",
        "--font-format=woff2",
        "--bbox=papersize",
        f"--output={svg_path.name}",
        dvi_path.name,
    ]
    proc = subprocess.run(dvisvgm_cmd, cwd=build_dir, capture_output=True, text=True)
    if proc.returncode != 0 or not svg_path.exists():
        last_good = _last_good_for(build_dir, name_hint)
        log = (proc.stderr or proc.stdout)
        # Clean compile intermediates we won't need.
        for ext in (".aux", ".log", ".dvi"):
            p = build_dir / f"{stem}{ext}"
            if p.exists():
                p.unlink()
        if last_good:
            return IslandResult(
                svg_path=last_good,
                rel_path=rel(last_good),
                cache_hit=False,
                stale=True,
                error=log,
            )
        placeholder = _placeholder_svg(stem, log)
        svg_path.write_text(placeholder, encoding="utf-8")
        return IslandResult(
            svg_path=svg_path,
            rel_path=rel(svg_path),
            cache_hit=False,
            stale=True,
            error=log,
        )

    # Clean compile-time intermediates; keep .tex for traceability and .svg as output.
    for ext in (".aux", ".log", ".dvi"):
        p = build_dir / f"{stem}{ext}"
        if p.exists():
            p.unlink()

    return IslandResult(svg_path=svg_path, rel_path=rel(svg_path), cache_hit=False)


def _placeholder_svg(stem: str, log_tail: str) -> str:
    """A small SVG that says "compile failed" — used when no last-good exists."""
    safe = (log_tail or "")[-300:].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="120" viewBox="0 0 500 120">\n'
        '  <rect width="500" height="120" fill="#fff5e8" stroke="#b85c00" stroke-width="1.5"/>\n'
        f'  <text x="14" y="28" font-family="monospace" font-size="13" fill="#b85c00">[!] compile failed for: {stem}</text>\n'
        f'  <text x="14" y="50" font-family="monospace" font-size="11" fill="#6b6757">log tail: {safe[:80]}…</text>\n'
        '</svg>\n'
    )


def clean(build_dir: Path) -> int:
    """Remove all artifacts under build_dir. Returns count removed."""
    if not build_dir.exists():
        return 0
    n = sum(1 for _ in build_dir.iterdir())
    shutil.rmtree(build_dir)
    return n
