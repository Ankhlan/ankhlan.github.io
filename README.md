# ankhlan.github.io

A working notebook and the proof of concept for a real-time writing system
that combines TeX-quality typography for mathematics and figures with
HTML-native prose.

The site is its own demo. The pipeline that builds it is small enough to
read in one sitting.

## Architecture in one paragraph

Each post is a single markdown file with YAML frontmatter and a body that
may contain fenced `tex-island` blocks. Each TeX island is a self-contained
`standalone` LaTeX document — typically a display equation or a TikZ
figure. At build time the pipeline walks `posts/`, extracts each island,
runs `latex` and then `dvisvgm --font-format=woff2` to produce one SVG per
island (cached by content hash), substitutes the islands into the markdown
as `<object>` references, renders the markdown to HTML through a Jinja2
template, and writes the result to `posts/<slug>/index.html`. Inline math
like `$x$` is rendered by KaTeX in the browser at read time. The output is
static HTML served by GitHub Pages.

## Layout

```
posts/<slug>/
  post.md            # source — YAML frontmatter + markdown + tex-island fences
  tex/build/         # SVG cache, gitignored
  index.html         # generated

templates/
  post.html.j2       # post layout
  index.html.j2      # site front page (post list)
  about.html.j2      # static About page

tools/
  build.py           # entrypoint — walks posts/, renders site
  render.py          # markdown + frontmatter + islands -> HTML
  tex_island.py      # one TeX block -> cached SVG

assets/
  css/tufte.css      # site CSS
  js/reader.js       # font controls

site.yaml            # site title and subtitle
.gitignore
requirements.txt
```

## Build

```
pip install -r requirements.txt
python tools/build.py
```

Cold build: ~2s per post with two TeX islands. Warm build (cache hit): ~10ms.

## Real-time writing loop

```
python tools/watch.py
```

Serves the site at <http://127.0.0.1:8765/> with file watching and live
reload. Edit `posts/<slug>/post.md`, save, the affected post recompiles
(islands cached by content hash so untouched figures don't rebuild), and
the browser tab reloads automatically. Pin the URL in a Chrome window on
a second monitor — that is the Zathura analog for this system.

## Author

Ankhlan Erdenebileg — monetary economist. Contact: <ankhlan.e@mongolbank.mn>.
