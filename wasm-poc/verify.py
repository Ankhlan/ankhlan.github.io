"""Headless verification of the WASM POC.

Loads http://127.0.0.1:8000/ in Playwright Chromium, waits for TikZJax to
render the figure, then reports what's in the DOM and what the console said.
Saves a screenshot to wasm-poc/_verify.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/"
HERE = Path(__file__).resolve().parent
SHOT = HERE / "_verify.png"


def main() -> int:
    console_messages: list[tuple[str, str]] = []
    page_errors: list[str] = []
    network_failures: list[str] = []
    tikz_requests: list[tuple[str, int]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1500, "height": 950})
        page = ctx.new_page()
        page.on("console", lambda msg: console_messages.append((msg.type, msg.text)))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("requestfailed",
                lambda req: network_failures.append(
                    f"{req.method} {req.url} -- {req.failure}"))
        page.on("response",
                lambda res: tikz_requests.append((res.url, res.status))
                    if "tikzjax" in res.url or "wasm" in res.url else None)

        page.goto(URL, wait_until="domcontentloaded")
        # Poll up to 30s for TikZJax to produce an <svg> in the preview.
        try:
            page.wait_for_function(
                "document.querySelectorAll('#preview svg').length > 0",
                timeout=30000,
            )
        except Exception:
            pass  # we'll report on whatever state we got
        page.wait_for_timeout(500)

        # Inspect TikZJax loading state
        tikzjax_globals = page.evaluate("""
        ({
          process: typeof window.process !== 'undefined' ? 'present' : 'missing',
          tikzjax: typeof window.tikzjax !== 'undefined' ? 'present' : 'missing',
          dvi2html: typeof window.dvi2html !== 'undefined' ? 'present' : 'missing',
          scripts: Array.from(document.querySelectorAll('script')).map(s => s.src).filter(x=>x).slice(-10),
          tikz_script_attrs: Array.from(document.querySelectorAll('script[type="text/tikz"]')).map(s => ({
            content_len: s.textContent.length,
            data_attrs: Array.from(s.attributes).map(a => a.name + '=' + a.value),
          })),
        })
        """)
        print(f"tikzjax globals       : {tikzjax_globals}")
        editor_text = page.evaluate("document.getElementById('editor').value")
        preview_html_len = page.evaluate("document.getElementById('preview').innerHTML.length")
        preview_text = page.evaluate("document.getElementById('preview').innerText")
        status_text = page.evaluate("document.getElementById('status-text').textContent")
        word_count = page.evaluate("document.getElementById('word-count').textContent")
        island_count = page.evaluate("document.getElementById('island-count').textContent")
        render_time = page.evaluate("document.getElementById('render-time').textContent")
        svg_in_preview = page.evaluate(
            "document.querySelectorAll('#preview svg').length"
        )
        katex_count = page.evaluate(
            "document.querySelectorAll('#preview .katex').length"
        )
        tikz_script_remaining = page.evaluate(
            "document.querySelectorAll('#preview script[type=\"text/tikz\"]').length"
        )

        page.screenshot(path=str(SHOT), full_page=False)
        browser.close()

    print("=" * 60)
    print("WASM POC verification report")
    print("=" * 60)
    print(f"editor textarea chars : {len(editor_text)}  (sample first 80: {editor_text[:80]!r})")
    print(f"preview innerHTML len : {preview_html_len}")
    print(f"preview text first 80 : {preview_text[:80]!r}")
    print(f"status-text bar       : {status_text!r}")
    print(f"word count            : {word_count}")
    print(f"island count          : {island_count}")
    print(f"render time           : {render_time}")
    print(f"<svg> in preview      : {svg_in_preview}")
    print(f".katex spans          : {katex_count}")
    print(f"unrendered tikz tags  : {tikz_script_remaining}")
    print(f"page errors           : {len(page_errors)}")
    for e in page_errors:
        print(f"  - {e}")
    print(f"console messages      : {len(console_messages)}")
    interesting = [(t, m) for t, m in console_messages if t in ("error", "warning")]
    for t, m in interesting:
        print(f"  [{t}] {m[:200]}")
    print(f"network failures      : {len(network_failures)}")
    for f in network_failures[:10]:
        print(f"  - {f}")
    print(f"tikz/wasm requests    : {len(tikz_requests)}")
    for url, status in tikz_requests[:15]:
        print(f"  {status}  {url}")
    print(f"screenshot saved      : {SHOT}")
    print("=" * 60)

    # Verdict
    issues = []
    if len(editor_text) < 200:
        issues.append("editor empty or near-empty")
    if preview_html_len < 200:
        issues.append("preview empty")
    if svg_in_preview == 0:
        issues.append("no SVG (TikZJax did not render)")
    if katex_count == 0:
        issues.append("no .katex spans (KaTeX did not render math)")
    if tikz_script_remaining > 0:
        issues.append(f"{tikz_script_remaining} tikz script tag(s) still pending")
    if page_errors:
        issues.append(f"{len(page_errors)} page error(s)")
    if issues:
        print("ISSUES:")
        for i in issues:
            print(f"  X{i}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
