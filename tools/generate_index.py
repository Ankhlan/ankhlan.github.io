#!/usr/bin/env python3
"""
generate_index.py — Parse article folders and print an index (placeholder).

Each article lives in posts/<slug>/ with an index.md containing YAML frontmatter.
Extend this to rewrite index.html, topics.html, and rss.xml.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO / "posts"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)

def parse_frontmatter(text: str) -> dict:
    """Extract YAML-ish frontmatter as a simple dict (no full YAML parser)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)
    data = {}
    for line in block.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip().strip('"').strip("'")
    return data

def main():
    posts = []
    
    # Scan article folders (each should have index.md)
    for folder in sorted(POSTS_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        index_md = folder / "index.md"
        if not index_md.exists():
            continue
        text = index_md.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        if meta.get("title"):
            posts.append({
                "slug": folder.name,
                "title": meta.get("title", folder.name),
                "date": meta.get("date", ""),
                "summary": meta.get("summary", ""),
                "tags": meta.get("tags", ""),
            })

    print("=== Post Index ===\n")
    for p in posts:
        print(f"{p['date']}  {p['title']}")
        print(f"           posts/{p['slug']}/")
        if p["summary"]:
            print(f"           {p['summary'][:60]}...")
        print()

    # TODO: Extend to rewrite index.html, topics.html, rss.xml

if __name__ == "__main__":
    main()
