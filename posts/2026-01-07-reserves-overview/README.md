# Reserves Overview

Article-specific assets for "Central Bank Reserves: A Quick Overview".

## Structure

```
2026-01-07-reserves-overview/
├── index.md          # Article text (Markdown + YAML frontmatter)
├── data/
│   └── reserves.csv  # Source data for this article
├── scripts/
│   └── plot_reserves.py  # Generates figures/
├── figures/
│   └── reserves-ex-gold.png  # Generated chart
└── README.md         # This file
```

## Regenerate figures

```bash
python scripts/plot_reserves.py
```
