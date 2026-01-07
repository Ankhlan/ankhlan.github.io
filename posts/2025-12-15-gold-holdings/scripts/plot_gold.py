#!/usr/bin/env python3
"""Generate gold purchases chart."""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ARTICLE_DIR = SCRIPT_DIR.parent
DATA_PATH = ARTICLE_DIR / "data" / "gold-purchases.csv"
FIG_PATH = ARTICLE_DIR / "figures" / "gold-purchases.png"

def main():
    df = pd.read_csv(DATA_PATH)
    
    # Pivot for stacked area
    pivot = df.pivot(index="date", columns="country", values="purchases_tonnes").fillna(0)
    
    fig, ax = plt.subplots(figsize=(8, 4))
    
    colors = {"China": "#E63946", "Russia": "#457B9D", "India": "#2A9D8F", "Turkey": "#E9C46A"}
    
    pivot.plot.bar(ax=ax, stacked=True, color=[colors.get(c, "#999") for c in pivot.columns], width=0.8)
    
    ax.set_title("Central Bank Gold Purchases (tonnes)", fontsize=12)
    ax.set_xlabel("")
    ax.set_ylabel("Tonnes")
    ax.legend(loc="upper left", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    # Rotate x labels
    plt.xticks(rotation=45, ha="right")
    
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Saved {FIG_PATH}")

if __name__ == "__main__":
    main()
