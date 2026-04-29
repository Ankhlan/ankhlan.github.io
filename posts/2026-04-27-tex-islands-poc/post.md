---
title: "TeX islands in HTML and Real Time writing system — proof of concept"
date: 2026-04-28
tags: [meta, infrastructure]
summary: "First post in the new pipeline. Prose flows in HTML; equations and TikZ figures render as TeX-quality SVG islands."
---

This post is the first one written in the new pipeline. The architecture is a
hybrid: prose lives in plain HTML so the browser can do what browsers are good
at — reflow, search, accessibility, copy-paste, mobile rendering — while
mathematics and figures are compiled by TeX, exported as SVG via
`dvisvgm`, and embedded as islands inside the HTML body.

The point of the experiment is to test whether the seam between two very
different layout engines holds in practice.

## A simple equation

The price of a coupon bond is the present value of its cash flows discounted
at the yield to maturity. With coupon $C_t$, face value $F$, and yield $y$, the
price has a familiar closed form, and Macaulay duration $D$ falls out as a
weighted average of cash-flow times:

```tex-island name=eq-bond-price alt="Bond price and Macaulay duration formulas"
\documentclass[border=2pt]{standalone}
\usepackage{amsmath,amssymb}
\begin{document}
$\displaystyle
P = \sum_{t=1}^{T} \frac{C_t}{(1+y)^t} + \frac{F}{(1+y)^T}
\qquad
D = \frac{1}{P}\sum_{t=1}^{T} t \cdot \frac{C_t}{(1+y)^t}
$
\end{document}
```

Inline math like $C_t / (1+y)^t$ is rendered by KaTeX in the browser; display
math that benefits from real TeX (above) is compiled to SVG at build time and
embedded. The author chooses the cost.

## A figure

A stylised yield curve, drawn in TikZ at build time:

```tex-island name=fig-yield-curve class="tex-island" alt="Stylised yield curve"
\documentclass[border=4pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{plotmarks}
\begin{document}
\begin{tikzpicture}[x=1cm, y=1cm, font=\small]
  \draw[->, thick] (0,0) -- (7,0) node[right] {maturity};
  \draw[->, thick] (0,0) -- (0,4) node[above] {yield (\%)};
  \draw[domain=0.2:6.5, smooth, thick] plot (\x, {1.2 + 1.6*ln(\x+0.5)});
  \foreach \x/\lab in {1/1y, 2/2y, 5/5y}
    \draw (\x,0.05) -- (\x,-0.05) node[below] {\lab};
  \node[anchor=north east] at (6.5, 3.6) {sample curve};
\end{tikzpicture}
\end{document}
```

## More on the real-time writing

Live TeXing once was one of the hardest things to create in real time. The whole post lives in one file. Now in the new agentic era we can compose research crunch data at the speed of thought in real time. And publish at real time. 
where the prose references it; there is no separate `figures/` folder to keep
in sync, no `\includegraphics{}` to chase down. Editing an equation is editing
the markdown; the build watcher recompiles only the islands whose source
changed (cached by content hash) and reloads the page.

The web does prose well. TeX does math and diagrams well. The seam between
them is an `<object>` tag — small, honest, and entirely under the author's
control.

> Demo edit from the agent — if you can read this in your writer without -- I can see this.
> having typed it, the live agent–editor loop is working. I dont see agent conversing with me on this code!
Aha you can read my code edits! but your spawninnig ghost agent just died!