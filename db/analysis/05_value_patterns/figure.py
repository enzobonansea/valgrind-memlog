#!/usr/bin/env python3
"""Figure 2 — per-bench bit-pattern shares of stored values, per alloc_type.

100% stacked horizontal bars over the disjoint partition recorded by Q05:
  zero                       (value == 0)
  nonzero_top_byte_zero      (value != 0 AND (value >> 56) == 0)
  nonzero_top_byte_nonzero   (rest)

These are exact bit-pattern shares — no claim is made about whether the
underlying value is a float, an int, or a pointer.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

CATEGORIES = [
    ("zero",                     "value == 0",            "#999999"),
    ("nonzero_top_byte_zero",    "0 < |value| < 2^56",    "#0072B2"),
    ("nonzero_top_byte_nonzero", "|value| ≥ 2^56",        "#E69F00"),
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
        sub = (df[df["alloc_type"] == atype]
               .set_index("bench").reindex(bench_order))
        y    = range(len(sub))
        left = [0.0] * len(sub)
        for col, _, color in CATEGORIES:
            vals = sub[f"{col}_frac"].fillna(0).to_numpy()
            ax.barh(y, vals, left=left, color=color,
                    edgecolor="white", linewidth=0.3, label=col)
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

    handles = [plt.Rectangle((0, 0), 1, 1, color=color, label=f"{col}\n({desc})")
               for col, desc, color in CATEGORIES]
    axes[-1].legend(handles=handles, loc="center left",
                    bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=8, title="bit pattern")
    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
