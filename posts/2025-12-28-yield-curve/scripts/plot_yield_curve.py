#!/usr/bin/env python3
"""Generate yield curve chart."""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ARTICLE_DIR = SCRIPT_DIR.parent
DATA_PATH = ARTICLE_DIR / "data" / "yields.csv"
FIG_PATH = ARTICLE_DIR / "figures" / "yield-curve.png"

def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # Plot the most recent curve as a line
    latest = df.iloc[-1]
    maturities = [2, 5, 10, 30]
    yields = [latest["2y"], latest["5y"], latest["10y"], latest["30y"]]
    
    ax.plot(maturities, yields, "o-", color="#457B9D", linewidth=2, markersize=8, label=f"Current ({latest['date'].strftime('%b %Y')})")
    
    # Plot historical for comparison
    first = df.iloc[0]
    yields_first = [first["2y"], first["5y"], first["10y"], first["30y"]]
    ax.plot(maturities, yields_first, "s--", color="#E9C46A", linewidth=1.5, markersize=6, alpha=0.7, label=f"Jan 2023")
    
    ax.set_xlabel("Maturity (years)")
    ax.set_ylabel("Yield (%)")
    ax.set_title("US Treasury Yield Curve", fontsize=12)
    ax.set_xticks(maturities)
    ax.set_xticklabels(["2Y", "5Y", "10Y", "30Y"])
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Saved {FIG_PATH}")

if __name__ == "__main__":
    main()
