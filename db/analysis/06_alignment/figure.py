#!/usr/bin/env python3
"""Figure 6 — alignment shares per bench × alloc_type.

100% stacked horizontal bars over the disjoint partition aligned_8B /
aligned_4B_only / unaligned, faceted by alloc_type. Tells compression-
scheme designers what alignment they can assume.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

CATEGORIES = [
    ("aligned_8B",      "8-byte aligned",      "#0072B2"),
    ("aligned_4B_only", "4-byte aligned only", "#56B4E9"),
    ("unaligned",       "unaligned",           "#CC79A7"),
]
ORDER = ["64bits", "32bits", "object"]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    for col, _, _ in CATEGORIES:
        df[f"{col}_frac"] = df[col] / df["total"].clip(lower=1)

    bench_order = (df.groupby("bench")["total"].sum()
                     .sort_values().index.tolist())

    fig, axes = plt.subplots(1, len(ORDER), figsize=(10.5, 6.5),
                              sharey=True)
    for ax, atype in zip(axes, ORDER):
        sub = (df[df.alloc_type == atype]
               .set_index("bench").reindex(bench_order))
        y    = range(len(sub))
        left = [0.0] * len(sub)
        for col, _, color in CATEGORIES:
            vals = sub[f"{col}_frac"].fillna(0).to_numpy()
            ax.barh(y, vals, left=left, color=color,
                    edgecolor="white", linewidth=0.3)
            left = [l + v for l, v in zip(left, vals)]
        ax.set_xlim(0, 1)
        ax.set_title(atype, fontsize=10)
        ax.set_xlabel("share of stores")
        ax.set_yticks(list(y))
        ax.set_yticklabels(sub.index, fontsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.grid(axis="x", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)

    handles = [plt.Rectangle((0, 0), 1, 1, color=color, label=desc)
               for _, desc, color in CATEGORIES]
    axes[-1].legend(handles=handles, loc="center left",
                    bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=9, title="alignment")
    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
