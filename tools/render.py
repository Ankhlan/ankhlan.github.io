r"""Render posts and site pages from sources into static HTML.

A post lives at posts/<slug>/post.md with this shape:

    ---
    title: ...
    date: 2026-04-27
    tags: [foo, bar]
    summary: ...
    ---
    Body markdown. Inline math like $x$ is rendered by KaTeX in-browser.
    Display math and TikZ figures live in fenced TeX islands:

        ```tex-island name=fig-yield
        \documentclass[border=4pt]{standalone}
        ...
        \end{document}
        ```

Site-level config (title, subtitle) lives in site.yaml at the repo root.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

from tex_island import compile_island

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
SITE_CONFIG = REPO / "site.yaml"

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
ISLAND_FENCE_RE = re.compile(
    r"^```tex-island(?P<attrs>[^\n]*)\n(?P<body>.*?)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
ATTR_RE = re.compile(r'(\w+)=("[^"]*"|\'[^\']*\'|\S+)')


@dataclass
class Post:
    slug: str
    frontmatter: dict
    body_md: str
    out_path: Path
    src_path: Path

    @property
    def title(self) -> str:
        return self.frontmatter.get("title", self.slug)

    @property
    def date(self) -> str:
        d = self.frontmatter.get("date", "")
        return str(d) if d else ""

    @property
    def summary(self) -> str:
        return self.frontmatter.get("summary", "")

    @property
    def tags(self) -> list[str]:
        return list(self.frontmatter.get("tags") or [])


@lru_cache(maxsize=1)
def site_config() -> dict:
    if not SITE_CONFIG.exists():
        return {"site_title": "Notebook", "site_subtitle": ""}
    return yaml.safe_load(SITE_CONFIG.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=1)
def jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def parse_post(post_md: Path) -> Post:
    text = post_md.read_text(encoding="utf-8")
    fm: dict = {}
    body = text
    m = FRONTMATTER_RE.match(text)
    if m:
        fm = yaml.safe_load(m.group(1)) or {}
        body = text[m.end():]
    return Post(
        slug=post_md.parent.name,
        frontmatter=fm,
        body_md=body,
        out_path=post_md.parent / "index.html",
        src_path=post_md,
    )


def _parse_attrs(s: str) -> dict:
    return {k: v.strip('"').strip("'") for k, v in ATTR_RE.findall(s)}


def substitute_islands(body_md: str, post_dir: Path) -> tuple[str, list[str]]:
    build_dir = post_dir / "tex" / "build"
    names: list[str] = []

    def replace(match: re.Match) -> str:
        attrs = _parse_attrs(match.group("attrs"))
        source = match.group("body").strip() + "\n"
        name_hint = attrs.get("name")
        result = compile_island(source, build_dir, name_hint=name_hint)
        names.append(name_hint or result.rel_path)
        alt = attrs.get("alt", name_hint or "TeX island")
        figclass = attrs.get("class", "tex-island")
        return (
            f'\n\n<object class="{figclass}" data="{result.rel_path}" '
            f'type="image/svg+xml" aria-label="{alt}"></object>\n\n'
        )

    return ISLAND_FENCE_RE.sub(replace, body_md), names


def render_markdown(body_md: str) -> str:
    md = MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
    md.enable(["table", "strikethrough"])
    return md.render(body_md)


def render_post(post_md: Path) -> Post:
    post = parse_post(post_md)
    rewritten_md, _ = substitute_islands(post.body_md, post_md.parent)
    body_html = render_markdown(rewritten_md)

    template = jinja_env().get_template("post.html.j2")
    rendered = template.render(
        body=body_html,
        title=post.title,
        date=post.date,
        summary=post.summary,
        tags=post.tags,
        slug=post.slug,
        **site_config(),
    )
    post.out_path.write_text(rendered, encoding="utf-8")
    return post


def render_index(posts: list[Post], repo_root: Path = REPO) -> Path:
    sorted_posts = sorted(posts, key=lambda p: p.date, reverse=True)
    template = jinja_env().get_template("index.html.j2")
    rendered = template.render(
        posts=[
            {"slug": p.slug, "title": p.title, "date": p.date, "summary": p.summary, "tags": p.tags}
            for p in sorted_posts
        ],
        **site_config(),
    )
    out = repo_root / "index.html"
    out.write_text(rendered, encoding="utf-8")
    return out


def render_about(repo_root: Path = REPO) -> Path:
    template = jinja_env().get_template("about.html.j2")
    rendered = template.render(**site_config())
    out = repo_root / "about.html"
    out.write_text(rendered, encoding="utf-8")
    return out


def render_all(posts_dir: Path) -> Iterable[Post]:
    for folder in sorted(posts_dir.iterdir()):
        if not folder.is_dir():
            continue
        post_md = folder / "post.md"
        if post_md.exists():
            yield render_post(post_md)


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "posts"
    if target.is_file():
        post = render_post(target)
        print(f"rendered {post.slug} -> {post.out_path}")
    else:
        for post in render_all(target):
            print(f"rendered {post.slug} -> {post.out_path}")
