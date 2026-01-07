# Notebook — Site Design

## Identity

A working notebook for a **monetary economist, trader, and central banker**.

The site publishes:
- Short notes and longer essays on money, reserves, yields, FX, and financial plumbing.
- Data-driven charts and tables (generated from Python scripts).
- Project threads that tie related notes together.

Tone: precise, skeptical, first-principles. Not a blog — a notebook of working ideas, some polished, some rough.

---

## Sections

| Page | Purpose |
|------|---------|
| **Home** | Latest posts + archive; one-liner intro. |
| **Topics** | Tag-based index: *Reserves & Gold*, *Yield Curves*, *FX & Flows*, *Monetary Systems*, *Market Structure*, *Central Banking*. |
| **Projects** | Multi-post threads: *Gold Notebook*, *Yield Curve Monitor*, *ECLIS Notes*, etc. |
| **Data** | (future) Interactive dashboards or downloadable datasets. |
| **About** | Short bio, contact, disclaimers. |

---

## Visual Design

- **Layout:** Tufte-inspired — narrow text column (~600px), wide right margin for sidenotes.
- **Typography:** Serif body (EB Garamond), sans-serif headings/nav (Source Sans 3).
- **Color:** Near-black text on off-white; muted accent for links; no heavy colors.
- **Charts:** Clean, minimal — matplotlib with seaborn whitegrid or custom style; consistent sizing.

---

## Content Workflow

```
posts/<slug>/
├── index.md          # Article (Markdown + YAML frontmatter)
├── data/             # Article-specific datasets
│   └── *.csv
├── scripts/          # Article-specific analysis
│   └── *.py
├── figures/          # Generated images (PNG/SVG)
│   └── *.png
└── README.md         # Optional: notes on regenerating
```

**Shared resources** (cross-article datasets, reusable code):
- `data/raw/`         — Original downloads (immutable)
- `data/processed/`   — Cleaned datasets used by multiple articles
- `analysis/`         — Shared Python utilities
- `assets/figures/`   — Site-wide images (logo, etc.)

**Build flow:**
```
┌─────────────────────┐
│ posts/<slug>/data/  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐      ┌─────────────────────┐
│ posts/<slug>/scripts│ ───► │ posts/<slug>/figures│
└─────────────────────┘      └─────────────────────┘
          │
          ▼
┌─────────────────────┐      ┌─────────────────────┐
│ posts/<slug>/index.md│───► │ posts/<slug>/index.html│
└─────────────────────┘      └─────────────────────┘
          (pandoc)
```

- **Write** article in `posts/<slug>/index.md`
- **Add data** to `posts/<slug>/data/`
- **Add scripts** to `posts/<slug>/scripts/`
- **Run** `tools/build.ps1` to regenerate all articles
- **Commit** and push; GitHub Pages serves static HTML

---

## Topic Tags

Core tags (expand as needed):

- `reserves` — central bank reserves, gold, FX holdings
- `gold` — gold market, revaluation, flows
- `yield-curve` — term structure, inversion, carry
- `fx` — exchange rates, flows, intervention
- `monetary-system` — plumbing, correspondent banking, settlements
- `market-structure` — liquidity, microstructure, order flow
- `central-banking` — policy, balance sheets, operations
- `macro` — broad macro takes
- `data` — dataset releases, sourcing notes

---

## Future Enhancements

- [ ] RSS feed (auto-generated)
- [ ] Client-side search (FlexSearch)
- [ ] Dark mode (`prefers-color-scheme`)
- [ ] Interactive charts (Plotly or Observable embeds)
- [ ] PDF export for selected essays (pandoc → LaTeX)

---

## File Naming Convention

Articles: `posts/YYYY-MM-DD-slug/` folder containing:
- `index.md` — article content
- `data/` — article-specific data
- `scripts/` — article-specific analysis
- `figures/` — generated outputs

Shared scripts: `analysis/<topic>_<description>.py`

Shared data: `data/raw/` (immutable), `data/processed/` (derived)

---

*Last updated: 2026-01-07*
