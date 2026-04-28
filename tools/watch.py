"""Run an incremental build and a live-reloading dev server.

Usage:
    python tools/watch.py [port]   # default port 8765

Watches posts/, templates/, and site.yaml. Any change rebuilds the affected
outputs and triggers a browser reload. Pin the served URL in a Chrome tab on
a second monitor — that is the Zathura analog.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build import main as run_build  # noqa: E402
from livereload import Server  # noqa: E402


def rebuild() -> None:
    print("=== change detected — rebuilding ===")
    run_build([])


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 8765

    run_build([])

    server = Server()
    # Watch sources; rebuild on change.
    server.watch(str(REPO / "posts" / "**" / "*.md"), rebuild, delay=0.2)
    server.watch(str(REPO / "posts" / "**" / "*.tex"), rebuild, delay=0.2)
    server.watch(str(REPO / "templates" / "**" / "*"), rebuild, delay=0.2)
    server.watch(str(REPO / "site.yaml"), rebuild, delay=0.2)
    # Watch CSS/JS for direct reload (no rebuild needed).
    server.watch(str(REPO / "assets" / "**" / "*"), delay=0.1)

    print(f"\nserving http://127.0.0.1:{port}/  (Ctrl+C to stop)\n")
    server.serve(port=port, host="127.0.0.1", root=str(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
