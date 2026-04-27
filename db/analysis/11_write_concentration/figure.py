#!/usr/bin/env python3
"""Write-concentration percentiles per bench.

Dot plot: y-axis is bench, x-axis is the number of buffers needed to absorb
50 / 80 / 90 / 95 / 99 % of stores (log scale). The horizontal spread per
bench summarises the long tail — a tight cluster on the left means a few
buffers carry almost everything; a wide spread means traffic is diffuse.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

PERCENTILES = [
    ("top_for_50pct", "50%", "#56B4E9"),
    ("top_for_80pct", "80%", "#0072B2"),
    ("top_for_90pct", "90%", "#009E73"),
    ("top_for_95pct", "95%", "#E69F00"),
    ("top_for_99pct", "99%", "#D55E00"),
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv").sort_values("top_for_99pct")
    benches = df["bench"].tolist()
    y       = range(len(benches))

    fig, ax = plt.subplots(figsize=(8.0, 6.5))
    for col, label, color in PERCENTILES:
        ax.scatter(df[col], y, color=color, label=label, s=40,
                   edgecolor="white", linewidth=0.5, zorder=3)

    ax.set_yticks(list(y))
    ax.set_yticklabels(benches, fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("# buffers needed to absorb percentile of stores (log)")
    ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(title="percentile", loc="lower right", frameon=False, fontsize=8)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
