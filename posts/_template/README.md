# Article Template

Copy this folder to create a new article:

```
posts/YYYY-MM-DD-slug/
├── index.md      # Your article (copy template below)
├── data/         # Article-specific data files
├── scripts/      # Python scripts to generate figures
├── figures/      # Generated images
└── README.md     # Optional notes
```

## index.md template

```markdown
---
title: "Your Title Here"
date: YYYY-MM-DD
tags: [tag1, tag2]
summary: "One-line summary for index pages."
---

# Your Title Here

Opening paragraph...

## Section

More text. Reference figures like this:

![Description](figures/my-chart.png)

---

*Posted YYYY-MM-DD. Tags: tag1, tag2.*
```

## scripts/example.py template

```python
#!/usr/bin/env python3
"""Generate figures for this article."""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ARTICLE_DIR = SCRIPT_DIR.parent
DATA_PATH = ARTICLE_DIR / "data" / "input.csv"
FIG_PATH = ARTICLE_DIR / "figures" / "output.png"

def main():
    df = pd.read_csv(DATA_PATH)
    
    fig, ax = plt.subplots(figsize=(7, 4))
    # ... your plot code ...
    
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight")
    print(f"Saved {FIG_PATH}")

if __name__ == "__main__":
    main()
```

## Build

From repo root:
```powershell
.\tools\build.ps1
```

This runs all `scripts/*.py` in each article folder and converts `index.md` to `index.html`.
