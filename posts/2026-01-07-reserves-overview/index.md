---
title: "Central Bank Reserves: A Quick Overview"
date: 2026-01-07
tags: [reserves, central-banking, data]
summary: "A short note on what central bank reserves are, why they matter, and how to track them."
---

# Central Bank Reserves: A Quick Overview

Central bank reserves are the assets held by a monetary authority to back liabilities (currency, bank reserves) and to intervene in markets. They typically include:

- **Foreign exchange** (USD, EUR, etc.)
- **Gold** (valued at market or book price)
- **SDRs and IMF reserve position**
- **Other claims** (e.g., bilateral swap lines)

## Why track reserves?

1. **Policy signal:** Changes in reserves reflect intervention, valuation, or portfolio shifts.
2. **Creditworthiness:** For emerging markets, reserve adequacy affects sovereign risk.
3. **Systemic flows:** Large moves can indicate stress or rebalancing across the system.

## Data sources

- **IMF COFER:** Currency composition of official foreign exchange reserves (quarterly, aggregate).
- **National central banks:** Many publish monthly or weekly reserve data.
- **World Gold Council:** Gold holdings by central bank.

## A simple chart

The figure below shows total reserves (ex gold) for a sample of countries.

![Reserves ex gold, selected countries](figures/reserves-ex-gold.png)

This chart is generated from `scripts/plot_reserves.py` using data in `data/reserves.csv`.

## Next steps

- Track changes month-over-month.
- Decompose into valuation vs. flow effects.
- Compare reserve adequacy metrics (import cover, short-term debt cover).

---

*Posted 2026-01-07. Tags: reserves, central-banking, data.*
