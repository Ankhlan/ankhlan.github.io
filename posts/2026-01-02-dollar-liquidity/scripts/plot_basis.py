#!/usr/bin/env python3
"""Generate cross-currency basis chart."""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ARTICLE_DIR = SCRIPT_DIR.parent
DATA_PATH = ARTICLE_DIR / "data" / "basis.csv"
FIG_PATH = ARTICLE_DIR / "figures" / "xccy-basis.png"

def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    
    fig, ax = plt.subplots(figsize=(8, 4))
    
    ax.plot(df["date"], df["eurusd_basis"], "-", color="#457B9D", linewidth=2, label="EUR/USD basis")
    ax.plot(df["date"], df["jpyusd_basis"], "-", color="#E63946", linewidth=2, label="JPY/USD basis")
    
    ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
    ax.fill_between(df["date"], df["eurusd_basis"], 0, alpha=0.1, color="#457B9D")
    ax.fill_between(df["date"], df["jpyusd_basis"], 0, alpha=0.1, color="#E63946")
    
    ax.set_ylabel("Basis (bp)")
    ax.set_title("Cross-Currency Basis Spreads (3M)", fontsize=12)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    # Annotate March 2020
    ax.annotate("COVID stress", xy=(pd.Timestamp("2020-03-15"), -100), fontsize=8, ha="center")
    
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Saved {FIG_PATH}")

if __name__ == "__main__":
    main()
