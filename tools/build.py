"""Build entrypoint.

Renders every post (posts/<slug>/post.md) and the two site pages
(index.html, about.html) into static HTML at the repo root and
under each post folder.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from render import render_all, render_index, render_about  # noqa: E402


def main(argv: list[str]) -> int:
    posts_dir = REPO / "posts"
    if not posts_dir.exists():
        print(f"posts directory not found: {posts_dir}", file=sys.stderr)
        return 1

    start = time.perf_counter()
    posts = list(render_all(posts_dir))
    index_path = render_index(posts)
    about_path = render_about()
    elapsed = time.perf_counter() - start

    for post in posts:
        print(f"  post   {post.slug:<40} {post.out_path.relative_to(REPO)}")
    print(f"  index                                            {index_path.relative_to(REPO)}")
    print(f"  about                                            {about_path.relative_to(REPO)}")
    print(f"\nbuilt {len(posts)} post(s) + 2 page(s) in {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
