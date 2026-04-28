"""Minimal isolated test: does TikZJax v1 from tikzjax.com work at all?

Loads the minimal test page (one static <script type="text/tikz">), waits up
to 60 seconds for an <svg> to appear, reports all network activity and
console messages.
"""

from __future__ import annotations

import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/tikzjax-minimal.html"


def main() -> int:
    console = []
    errors = []
    requests = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("console", lambda m: console.append((m.type, m.text)))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", lambda r: requests.append((r.url, r.status)))

        page.goto(URL, wait_until="domcontentloaded")
        try:
            page.wait_for_function(
                "document.querySelectorAll('#figure svg').length > 0",
                timeout=60000,
            )
            verdict = "TikZJax rendered (SVG present)"
        except Exception:
            verdict = "TikZJax FAILED to render after 60s"

        svgs = page.evaluate("document.querySelectorAll('#figure svg').length")
        tikz_pending = page.evaluate(
            "document.querySelectorAll('#figure script[type=\"text/tikz\"]').length"
        )
        page.screenshot(path="wasm-poc/_minimal_verify.png", full_page=True)
        browser.close()

    print(f"verdict: {verdict}")
    print(f"svgs in #figure: {svgs}")
    print(f"pending tikz tags: {tikz_pending}")
    print(f"page errors: {len(errors)}")
    for e in errors:
        print(f"  - {e[:200]}")
    print(f"console: {len(console)} messages")
    for t, m in console[:20]:
        print(f"  [{t}] {m[:200]}")
    print(f"network: {len(requests)} responses")
    for url, status in requests:
        print(f"  {status}  {url[:140]}")
    return 0 if svgs > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
