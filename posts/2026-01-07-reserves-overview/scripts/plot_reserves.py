#!/usr/bin/env python3
"""
plot_reserves.py — Generate reserves chart for this article.

Run from article folder or repo root:
    python scripts/plot_reserves.py
    python posts/2026-01-07-reserves-overview/scripts/plot_reserves.py
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Resolve paths relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
ARTICLE_DIR = SCRIPT_DIR.parent
DATA_PATH = ARTICLE_DIR / "data" / "reserves.csv"
FIG_PATH = ARTICLE_DIR / "figures" / "reserves-ex-gold.png"

def main():
    # Load data
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])

    # Pivot for plotting
    pivot = df.pivot(index="date", columns="country", values="reserves_bn_usd")

    # Plot
    fig, ax = plt.subplots(figsize=(7, 4))
    for col in pivot.columns:
        ax.plot(pivot.index, pivot[col], marker="o", label=col)

    ax.set_title("FX Reserves (ex gold), Selected Countries", fontsize=12)
    ax.set_ylabel("USD bn")
    ax.set_xlabel("")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Save
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight")
    print(f"Saved {FIG_PATH}")

if __name__ == "__main__":
    main()
