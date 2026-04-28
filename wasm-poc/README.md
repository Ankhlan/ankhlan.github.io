# wasm-poc — pure WASM writing tool, proof of concept

A single HTML file. No backend, no install. Editor on the left, live preview on
the right. Markdown via markdown-it. Inline / display math via KaTeX. TeX
islands compiled in the browser by TikZJax (LaTeX in WebAssembly). Files
read/saved via the browser's File System Access API where available;
otherwise via download.

## Run it

Easiest:

```
python -m http.server 8000 --directory wasm-poc
```

Then open <http://localhost:8000/> in Chrome or Edge (Chromium-based browsers
are needed for File System Access API; the tool works in Firefox/Safari but
falls back to download-style save).

You can also open `index.html` directly via `file://` — TikZJax loads from
its CDN, so first-paint needs internet.

## What's being tested

- **TikZJax fidelity and speed** — does the in-browser TeX produce SVGs
  comparable to the dvisvgm output we use server-side? How fast is cold
  compile vs. cache hit?
- **The render loop** — debounced (~180ms) markdown + math + island compile.
  Does the latency feel live?
- **The single-file authoring model** — fenced ` ```tex-island ` blocks with
  full `tikzpicture` content, alongside prose and KaTeX math.
- **File ergonomics** — open / save / export HTML, with localStorage as a
  draft fallback.

## What's not in this POC

- No agent / AI dispatch (BYOK Anthropic key + small backend comes later).
- No GitHub OAuth or repo sync (local files only).
- No CodeMirror — plain `<textarea>` so the moving parts are minimal.
- No publish pipeline (this is the *editor*; publishing is a separate concern).

## Known limitations of TikZJax

TikZJax v1 supports a subset of LaTeX packages: `tikz`, `pgfplots`,
`pgfornament`, common decorations / arrows / shapes / positioning libraries.
Custom packages or `\usepackage{...}` directives outside that subset will
fail. For islands that need a wider LaTeX surface, the eventual server-side
fallback (dvisvgm via the existing `tools/tex_island.py`) takes over — but
that's not in this POC.
