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

## Writing Tufte-Style Articles

Tufte's philosophy: **the reader's eye should flow down the main argument** while supporting material (notes, small figures, commentary) lives in the margin. This creates a layered reading experience.

### Figure Types

| Type | HTML Class | When to Use |
|------|-----------|-------------|
| **Margin Figure** | `margin-figure` | Small charts, supporting visuals, thumbnails |
| **Main Column** | `<figure>` (default) | Primary charts that drive the argument |
| **Full-width** | `fullwidth-figure` | Complex visualizations, multi-panel charts |

### HTML Patterns

**Margin figure** (floats right, ~280px wide):
```html
<figure class="margin-figure">
  <img src="figures/small-chart.png" alt="Description">
  <figcaption>Caption in margin</figcaption>
</figure>
```

**Sidenote** (numbered, appears in margin):
```html
<p>Main text continues here.<span class="sidenote-number"></span></p>
<span class="sidenote">This appears in the margin with a superscript number.</span>
```

**Margin note** (unnumbered, appears in margin):
```html
<span class="marginnote">Commentary without a number.</span>
```

**Full-width figure** (spans text + margin):
```html
<figure class="fullwidth-figure">
  <img src="figures/wide-chart.png" alt="Description">
  <figcaption>Caption below wide figure</figcaption>
</figure>
```

### Python Script Guidelines

Generate figures at appropriate sizes for each use case:

```python
import matplotlib.pyplot as plt

# For margin figures: narrow, compact
fig, ax = plt.subplots(figsize=(4, 3), dpi=150)
# ... plot ...
fig.savefig('figures/margin-chart.png', bbox_inches='tight', facecolor='#fdfaf5')

# For main column: medium width
fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
# ... plot ...
fig.savefig('figures/main-chart.png', bbox_inches='tight', facecolor='#fdfaf5')

# For full-width: wide format
fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
# ... plot ...
fig.savefig('figures/fullwidth-chart.png', bbox_inches='tight', facecolor='#fdfaf5')
```

**Style settings for Tufte aesthetics:**
```python
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.5,
    'axes.labelsize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'figure.facecolor': '#fdfaf5',
    'axes.facecolor': '#fdfaf5',
})
```

### Article Structure Example

```markdown
---
title: "Gold Holdings Analysis"
date: 2026-01-15
tags: [gold, reserves]
---

# Gold Holdings Analysis

The main argument starts here, flowing down the narrow column.

<figure class="margin-figure">
  <img src="figures/gold-trend.png" alt="Gold trend">
  <figcaption>20-year trend</figcaption>
</figure>

Central banks hold approximately 36,000 tonnes of gold.<span class="sidenote-number"></span>
<span class="sidenote">Source: World Gold Council, Q3 2025 data.</span>

## Key Findings

The primary visualization drives the main point:

<figure>
  <img src="figures/gold-holdings-by-country.png" alt="Holdings by country">
  <figcaption>Top 10 holders account for 70% of official gold.</figcaption>
</figure>

<span class="marginnote">Russia and China have been the largest buyers since 2010.</span>

For complex multi-panel analysis, use full-width:

<figure class="fullwidth-figure">
  <img src="figures/gold-decomposition.png" alt="Decomposition">
  <figcaption>Left: Buyers. Center: Sellers. Right: Net flow by year.</figcaption>
</figure>
```

### Responsive Behavior

- **Wide screens (1100px+):** Margins appear on the right; margin figures float beside text
- **Narrow screens:** Margins collapse inline; figures stack vertically with subtle left border

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
