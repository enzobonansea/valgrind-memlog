#!/usr/bin/env python3
"""Figure 3 — store traffic is dominated by a tiny set of allocations.

Per bench: cumulative share of total stores captured by the top-K hottest
allocations (K up to 20, which is what 02_top_allocations.csv records).
A line per bench, sorted by saturation height; reference line at 50%.

If the top-20 captures, say, >70% on most benches, that's a direct
argument for per-allocation-site optimization.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE    = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
OUT     = HERE / "fig3_concentration.svg"


def main() -> None:
    totals = pd.read_csv(RESULTS / "01_summary.csv")[["bench", "stores"]]
    top    = pd.read_csv(RESULTS / "02_top_allocations.csv")[["bench", "stores"]]

    # Top-20 are already in descending order per bench (LIMIT 20 ORDER BY stores).
    top["rank"] = top.groupby("bench").cumcount() + 1
    top = top.merge(totals.rename(columns={"stores": "total_stores"}), on="bench")
    top["cum_stores"] = top.groupby("bench")["stores"].cumsum()
    top["cum_frac"]   = top["cum_stores"] / top["total_stores"]

    final = (top.sort_values(["bench", "rank"])
                .groupby("bench")["cum_frac"].last()
                .sort_values(ascending=False))
    bench_order = final.index.tolist()

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    cmap = plt.get_cmap("viridis")
    for i, bench in enumerate(bench_order):
        sub = top[top["bench"] == bench].sort_values("rank")
        ax.plot(sub["rank"], sub["cum_frac"],
                marker="o", markersize=2.5, linewidth=1.0,
                color=cmap(i / max(1, len(bench_order) - 1)),
                label=bench, alpha=0.85)

    ax.axhline(0.5, color="black", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_xlabel("top-K hottest allocations (per bench)")
    ax.set_ylabel("cumulative share of bench's total stores")
    ax.set_xlim(1, 20)
    ax.set_ylim(0, 1.02)
    ax.grid(linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=7, ncol=1, title="bench")
    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
