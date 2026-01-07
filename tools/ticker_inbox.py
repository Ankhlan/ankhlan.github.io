import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _load_json_array(path: Path) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    out: list[str] = []
    for x in data:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def _save_json_array(path: Path, items: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Append an inbox message to data/ticker.json")
    ap.add_argument("--file", default="data/ticker.json")
    ap.add_argument("--text", required=True)
    ap.add_argument("--source", default="")
    ap.add_argument("--max-items", type=int, default=50)
    args = ap.parse_args()

    text = (args.text or "").strip()
    if not text:
        raise SystemExit("--text is required")

    # Keep ticker items short-ish
    text = " ".join(text.split())
    if len(text) > 160:
        text = text[:157] + "…"

    source = (args.source or "").strip()

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    prefix = f"[{source}] " if source else ""
    item = f"{prefix}{text} - {stamp}"

    path = Path(args.file)
    items = _load_json_array(path)

    # De-dupe exact repeats
    if items and items[0] == item:
        return 0

    items.insert(0, item)

    max_items = max(5, int(args.max_items))
    items = items[:max_items]

    _save_json_array(path, items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
