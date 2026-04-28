# Design

## What this site is

A working notebook on monetary economics, and simultaneously the proof of
concept for the writing system that publishes it.

## What problem the system solves

Markdown is convenient. TeX is beautiful. Browsers render markdown but
not TeX. Every prior attempt to bridge them — Pandoc HTML, MathJax,
`tex4ht`, LaTeXML — has had to choose between TeX-quality layout (giving
up reflow and accessibility) and reflowable HTML (giving up TeX-quality
layout). Writers who care about typography end up publishing PDFs.

This system makes the choice locally instead of globally. Prose lives in
HTML and gets web-native treatment: reflow, search, accessibility, mobile.
Mathematics and figures live in TeX and get TeX-native treatment: real
glyph positioning, microtype, TikZ. The seam between them is an
`<object>` tag — small, honest, and entirely under the author's control.

## Architecture

```
posts/<slug>/post.md
   │
   ├── YAML frontmatter ────────────► metadata (title/date/tags/summary)
   ├── Markdown prose
   │     │
   │     ├── inline $math$        ──► KaTeX (browser, read-time)
   │     ├── display $$math$$     ──► KaTeX (browser, read-time)
   │     └── ```tex-island fences ──► latex → dvisvgm → SVG (build-time, cached)
   │                                       │
   │                                       └── <object data="...svg">
   │                                                  │
   ▼                                                  ▼
markdown-it-py + Jinja2 template ◄──────────── substituted markdown
   │
   ▼
posts/<slug>/index.html
```

### Design decisions

1. **Single-source authoring.** The whole post lives in one markdown file.
   TeX islands are inline fenced blocks, not separate `.tex` files.
   Editing a figure means editing the markdown.

2. **Hybrid layout, not pure TeX-on-web.** Pure TeX-as-body (DVI → SVG for
   the entire post) was tested and rejected: the gains in prose typography
   are real but small, the losses in accessibility, search, and mobile
   reflow are substantial. The hybrid concentrates TeX where it earns its
   keep — math and figures — and lets HTML do prose.

3. **Content-addressed island cache.** Each TeX island's SVG is named by
   the SHA-256 of its source. Edit prose without recompiling islands; edit
   one island and only that one rebuilds. The cache lives at
   `posts/<slug>/tex/build/` and is gitignored.

4. **DVI is an intermediate, not canonical.** TeX source is the source of
   truth. DVI files are deterministic and ephemeral.

5. **Static output, no runtime.** The site is plain HTML, CSS, and a small
   amount of vendored JS (KaTeX, font controls). It is served by GitHub
   Pages. There is no analytics, no comment system, no client-side
   framework.

6. **The tool is unusual; the authorship is conventional.** The pipeline
   may be terminal-driven and AI-assisted at the editing surface. The
   published artifact is the author's. There is no AI byline, no
   conversation log in the margin, no co-authorship. The instrument is
   not a participant in the document.

## Roadmap

- File watcher with live-reload (the Zathura analog for the browser tab).
- Index generation enhancements: tags, archive, RSS.
- Optional second narrow geometry for mobile-readable TeX islands.

## Non-goals

- Reimplementing TeX, DVI, dvisvgm, KaTeX, or the markdown parser.
- A static site generator framework. The pipeline is ~300 lines of Python
  and is meant to stay that way.
- Co-authorship surfaces, AI annotations, or anything that puts the tool
  into the published artifact.
