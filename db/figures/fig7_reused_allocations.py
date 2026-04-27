#!/usr/bin/env python3
"""Figure 7 — top reused allocation slots.

Scatter: x = total stores landed at this address across reuses (log),
y = max generation count (log), point color = bench. Identifies allocator
hotspots — addresses that get malloc'd / free'd thousands of times.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE    = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
OUT     = HERE / "fig7_reused_allocations.svg"


def main() -> None:
    df = pd.read_csv(RESULTS / "07_reused_allocations.csv")
    if df.empty:
        print(f"no rows in 07_reused_allocations.csv — skipping")
        return

    benches  = sorted(df["bench"].unique())
    cmap     = plt.get_cmap("tab20")
    color_of = {b: cmap(i / max(1, len(benches) - 1)) for i, b in enumerate(benches)}

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    for bench in benches:
        sub = df[df["bench"] == bench]
        ax.scatter(sub["total_stores"], sub["max_generation"],
                   s=40, color=color_of[bench], edgecolor="white",
                   linewidth=0.5, label=bench, alpha=0.85)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("total stores at this address (log)")
    ax.set_ylabel("# reuses of the address (log)")
    ax.grid(which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=8, title="bench")
    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
