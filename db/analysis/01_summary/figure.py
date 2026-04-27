#!/usr/bin/env python3
"""Figure 1 — per-bench logged-store volume, broken down by alloc_type.

Horizontal stacked bars, log-x, sorted by total store count descending.
`alloc_type` reports the *alignment class* of the allocation behind each
store (8-byte / 4-byte / object), not whether the value is float or int.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

# Colorblind-safe (Wong palette).
COLORS = {"64bits": "#0072B2", "32bits": "#56B4E9", "object": "#E69F00"}


def main() -> None:
    df = pd.read_csv(HERE / "result.csv").sort_values("stores")

    fig, ax = plt.subplots(figsize=(6.0, 7.0))
    y       = range(len(df))
    left    = [0] * len(df)
    for col, label in [("stores_64bits", "64bits"),
                       ("stores_32bits", "32bits"),
                       ("stores_object", "object")]:
        ax.barh(y, df[col], left=left, color=COLORS[label],
                label=label, edgecolor="white", linewidth=0.4)
        left = [l + v for l, v in zip(left, df[col])]

    ax.set_yticks(list(y))
    ax.set_yticklabels(df["bench"], fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("logged stores (log scale)")
    ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(title="alloc_type", loc="lower right", frameon=False, fontsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
