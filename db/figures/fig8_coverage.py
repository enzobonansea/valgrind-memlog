#!/usr/bin/env python3
"""Figure 8 — write density per (bench, alloc_type).

Scatter: x = avg slot coverage (fraction of slots written), y = avg writes
per slot (log). Bubble area scales with the number of allocations behind
the point. Color = alloc_type.

Quadrants: low-coverage low-writes = sparse poking; high-coverage high-
writes = streaming/in-place updates; high-coverage low-writes = one-shot
zero-init. Picks out the regime each bench operates in.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE    = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
OUT     = HERE / "fig8_coverage.svg"

COLOR_OF = {"64bits": "#0072B2", "32bits": "#56B4E9"}  # 32/64 only in Q08


def main() -> None:
    df = pd.read_csv(RESULTS / "08_coverage.csv")
    df = df.dropna(subset=["avg_coverage", "avg_writes_per_slot"])

    fig, ax = plt.subplots(figsize=(8.0, 6.0))
    for atype in ("64bits", "32bits"):
        sub = df[df.alloc_type == atype]
        sizes = (sub["allocations"].clip(lower=1) ** 0.5) * 6.0
        ax.scatter(sub["avg_coverage"], sub["avg_writes_per_slot"],
                   s=sizes, color=COLOR_OF[atype], alpha=0.6,
                   edgecolor="white", linewidth=0.5, label=atype)
        for _, row in sub.iterrows():
            if row["allocations"] >= 100:
                ax.annotate(row["bench"],
                            (row["avg_coverage"], row["avg_writes_per_slot"]),
                            fontsize=7, alpha=0.7,
                            xytext=(4, 2), textcoords="offset points")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("avg coverage (slots written / total slots, log)")
    ax.set_ylabel("avg writes per written slot (log)")
    ax.grid(which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(loc="upper left", title="alloc_type", frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
