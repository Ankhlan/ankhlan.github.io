"""Build entrypoint.

Renders every post (posts/<slug>/post.md) and the two site pages
(index.html, about.html) into static HTML at the repo root and
under each post folder. Also writes posts.json — a manifest the
desk editor reads to populate its post list.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from render import render_all, render_index, render_about  # noqa: E402


def write_posts_manifest(posts, out: Path) -> None:
    """Emit posts.json — used by the desk editor's home view."""
    manifest = sorted(
        [
            {
                "slug": p.slug,
                "title": p.title,
                "date": p.date,
                "summary": p.summary,
                "tags": p.tags,
                "source": f"posts/{p.slug}/post.md",
            }
            for p in posts
        ],
        key=lambda r: r["date"],
        reverse=True,
    )
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str]) -> int:
    posts_dir = REPO / "posts"
    if not posts_dir.exists():
        print(f"posts directory not found: {posts_dir}", file=sys.stderr)
        return 1

    start = time.perf_counter()
    posts = list(render_all(posts_dir))
    index_path = render_index(posts)
    about_path = render_about()
    manifest_path = REPO / "posts.json"
    write_posts_manifest(posts, manifest_path)
    elapsed = time.perf_counter() - start

    for post in posts:
        print(f"  post   {post.slug:<40} {post.out_path.relative_to(REPO)}")
    print(f"  index                                            {index_path.relative_to(REPO)}")
    print(f"  about                                            {about_path.relative_to(REPO)}")
    print(f"  manifest                                         {manifest_path.relative_to(REPO)}")
    print(f"\nbuilt {len(posts)} post(s) + 2 page(s) + manifest in {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
