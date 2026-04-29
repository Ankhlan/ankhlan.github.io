"""Run an incremental build and a live-reloading dev server.

Usage:
    python tools/watch.py [port]   # default port 4321

Serves the repo at http://127.0.0.1:<port>/ with livereload.
Also starts a tiny API server at port+1 with one endpoint:

    POST /api/publish    body: {"message": "optional commit message"}
        runs tools/publish.py and returns the result as JSON

The desk editor's Publish button hits this endpoint. CORS is open
(`*`) so a desk page served from any origin (file://, github.io, etc.)
can call your local watcher while you write.

Watches posts/, templates/, pages/, site.yaml. Any change rebuilds the
affected outputs and triggers a browser reload.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build import main as run_build  # noqa: E402
from livereload import Server  # noqa: E402


def rebuild() -> None:
    print("=== change detected — rebuilding ===")
    run_build([])


# ---------------------------------------------------------------- API server

class APIHandler(BaseHTTPRequestHandler):
    """Tiny API: POST /api/publish runs tools/publish.py."""

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/publish":
            self._json(404, {"ok": False, "error": "not found"})
            return

        # Optional JSON body with a commit message.
        length = int(self.headers.get("Content-Length", "0") or "0")
        message = ""
        if length:
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                message = (payload.get("message") or "").strip()
            except Exception:
                message = ""

        cmd = [sys.executable, str(REPO / "tools" / "publish.py")]
        if message:
            cmd.append(message)

        print(f"[api] running publish.py" + (f" -- {message!r}" if message else ""))
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
        ok = proc.returncode == 0
        body = {
            "ok": ok,
            "code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        self._json(200 if ok else 500, body)

    def _json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:  # quiet by default
        pass


def start_api(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), APIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="desk-api")
    thread.start()
    return server


# ------------------------------------------------------------------- entry

def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 4321
    api_port = port + 1

    run_build([])

    api = start_api(api_port)
    print(f"api    http://127.0.0.1:{api_port}/api/publish  (POST)")

    server = Server()
    server.watch(str(REPO / "posts" / "**" / "*.md"), rebuild, delay=0.2)
    server.watch(str(REPO / "posts" / "**" / "*.tex"), rebuild, delay=0.2)
    server.watch(str(REPO / "pages" / "**" / "*.md"), rebuild, delay=0.2)
    server.watch(str(REPO / "templates" / "**" / "*"), rebuild, delay=0.2)
    server.watch(str(REPO / "site.yaml"), rebuild, delay=0.2)
    server.watch(str(REPO / "assets" / "**" / "*"), delay=0.1)

    print(f"site   http://127.0.0.1:{port}/")
    print(f"desk   http://127.0.0.1:{port}/desk/")
    print()
    try:
        server.serve(port=port, host="127.0.0.1", root=str(REPO))
    finally:
        api.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
