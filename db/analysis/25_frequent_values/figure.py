#!/usr/bin/env python3
"""Frequent-value coverage curves per (bench, alloc_type).

For each (bench, alloc_type) we plot the cumulative store-coverage of
the K most-frequent values for K ∈ {1, 8, 64, 256, 1024}. A line that
saturates near y=1 by x=64 means a 64-entry dictionary already
captures essentially all the writes (the frequent-value-compression
ideal); a line that stays flat across the x-axis means the bench has
high value diversity and dictionary compression won't help.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

CAPS = [1, 8, 64, 256, 1024]
COLS = ["top1_frac", "top8_frac", "top64_frac", "top256_frac", "top1024_frac"]
ATYPES = ["32bits", "64bits", "object"]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.0),
                             sharey=True)
    cmap = plt.get_cmap("turbo")

    benches = sorted(df["bench"].unique())
    color_of = {b: cmap(i / max(1, len(benches) - 1))
                for i, b in enumerate(benches)}

    for ax, atype in zip(axes, ATYPES):
        sub = df[df.alloc_type == atype].sort_values("bench")
        for _, r in sub.iterrows():
            y = [r[c] for c in COLS]
            ax.plot(CAPS, y, marker="o", markersize=3.5,
                    linewidth=1.0, alpha=0.85,
                    color=color_of[r["bench"]], label=r["bench"])

        ax.set_xscale("log")
        ax.set_xticks(CAPS)
        ax.set_xticklabels([str(c) for c in CAPS])
        ax.set_xlim(0.85, 1200)
        ax.set_ylim(-0.03, 1.03)
        ax.set_title(atype, fontsize=10)
        ax.set_xlabel("# most-frequent values (dictionary size)", fontsize=9)
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(which="both", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for thr in (0.5, 0.9):
            ax.axhline(thr, color="#bbb", lw=0.5, linestyle="--", zorder=1)

    axes[0].set_ylabel("cumulative store coverage", fontsize=9)
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=7, title="bench",
                    title_fontsize=7, ncol=1)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
