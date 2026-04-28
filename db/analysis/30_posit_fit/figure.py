#!/usr/bin/env python3
"""Posit-32 suitability: high-precision regime share per (bench, alloc_type).

Horizontal bars: x = fraction of stores in the posit "high-precision"
regime (low |unbiased exponent|, where posits beat IEEE-32). Faceted by
alloc_type.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

COLOR = {"64bits": "#0072B2", "32bits": "#56B4E9", "object": "#E69F00"}
ORDER = ["64bits", "32bits", "object"]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    bench_order = (df.groupby("bench")["frac_high_precision"].max()
                     .sort_values().index.tolist())

    fig, axes = plt.subplots(1, len(ORDER), figsize=(10.5, 6.5),
                              sharey=True)
    for ax, atype in zip(axes, ORDER):
        sub = (df[df.alloc_type == atype]
               .set_index("bench").reindex(bench_order))
        ax.barh(range(len(sub)), sub["frac_high_precision"].fillna(0),
                color=COLOR[atype], edgecolor="white", linewidth=0.4)
        ax.set_yticks(range(len(sub)))
        ax.set_yticklabels(sub.index, fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_xlabel("share in posit high-precision regime")
        ax.set_title(atype, fontsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
