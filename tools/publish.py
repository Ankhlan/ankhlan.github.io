"""publish.py — one-command publish for ankhlan.github.io.

Builds the site, commits everything, pushes to origin/main. GitHub Pages
deploys within ~30–90 seconds.

Usage:
    python tools/publish.py                 # auto commit message
    python tools/publish.py "your message"  # explicit commit message
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path = REPO, capture: bool = False) -> tuple[int, str]:
    """Run a command, optionally capturing output. Returns (code, combined stdout+stderr)."""
    print(f"$ {' '.join(cmd)}", flush=True)
    if capture:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
        text = (proc.stdout or "") + (proc.stderr or "")
        if text.strip():
            print(text.rstrip())
        return proc.returncode, text
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode, ""


def main(argv: list[str]) -> int:
    # 1. Build the site so generated HTML is current.
    code, _ = run([sys.executable, str(REPO / "tools" / "build.py")])
    if code != 0:
        print("[!] build failed — fix and re-run", file=sys.stderr)
        return 1

    # 2. Stage all changes.
    code, _ = run(["git", "add", "-A"])
    if code != 0:
        return 1

    # 3. Anything to commit?
    code, _ = run(["git", "diff", "--cached", "--quiet"], capture=True)
    if code == 0:
        print("\nnothing to publish — working tree matches origin")
        return 0

    # 4. Commit.
    msg = argv[0] if argv else f"Publish {time.strftime('%Y-%m-%d %H:%M')}"
    code, _ = run(["git", "commit", "-m", msg])
    if code != 0:
        return 1

    # 5. Push.
    code, _ = run(["git", "push", "origin", "main"])
    if code != 0:
        print("[!] push failed — see above", file=sys.stderr)
        return 1

    print("\npublished. live at https://ankhlan.github.io within 30–90 seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
