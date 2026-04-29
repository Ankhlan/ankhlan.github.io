# desk — writing surface for ankhlan.github.io

Single HTML file. Two views (post list + editor). Live preview with markdown,
KaTeX inline math, and TikZJax-rendered TeX islands. Files read via fetch (when
served from the same origin as the post repo) and saved back via the File
System Access API in Chromium-based browsers. Falls back to download in others.

## Run

```
python tools/watch.py 4321         # in repo root — runs the watcher + livereload
```

Then open <http://127.0.0.1:4321/desk/>.

Or live: <https://ankhlan.github.io/desk/>.

## Views

- **`/desk/`** — post list, "+ new post", "Open .md" (loads any markdown file from disk into the editor with a writable handle).
- **`/desk/?edit=posts/<slug>/post.md`** — editor for that post, with live preview. Click "Open .md" to point the editor at the same file on disk for writing.

## Loop

- Type in the editor → debounced 120 ms → preview rerenders.
- File handle present (Open .md was used) → autosave 200 ms after typing pause.
- Otherwise → status shows "modified"; click Download to save manually.
- TeX islands render via TikZJax on initial load. To re-render after editing
  inside a `tex-island` fence, reload the page (TikZJax v1 limitation).

## Publish

Use the terminal: `python tools/publish.py "your message"` from the repo
root. Builds, commits, pushes; ankhlan.github.io updates within ~30–90 s.
