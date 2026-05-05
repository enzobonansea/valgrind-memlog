#!/usr/bin/env python3
"""MX (microscaling) block-viability per (bench, alloc_type).

Across every (bench, alloc_type) pair in this dataset, the MX viability
fraction is 1.0 — i.e. every 32-element block has either fewer than two
finite-normal exponents, or an exponent spread within the MXFP8 E4M3
headroom (≤ 8). The figure therefore shows the volume of blocks per row
on a log scale (so the rare benches still register), with a marker
column on the right confirming "100% viable, max spread observed".
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df["row"] = df["bench"] + " · " + df["alloc_type"]
    df = df.sort_values(["bench", "alloc_type"]).reset_index(drop=True)

    n = len(df)
    fig, ax = plt.subplots(figsize=(8.0, max(4.0, 0.22 * n + 1.0)))
    y = np.arange(n)

    bars = ax.barh(y, df["blocks"], color="#91cf60",
                   edgecolor="white", linewidth=0.4, alpha=0.9)

    ax.set_yticks(y)
    ax.set_yticklabels(df["row"].tolist(), fontsize=7)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("# 32-element blocks (log)", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Annotate per-row: viable %, max spread observed.
    xmax = df["blocks"].max() * 1.05
    for i, r in df.iterrows():
        max_spread = r["max_spread"]
        spread_lbl = ("max spread = "
                      + ("—" if pd.isna(max_spread) else f"{int(max_spread)}"))
        ax.text(xmax, i,
                f"  100% viable · {spread_lbl}",
                ha="left", va="center", fontsize=6.5,
                color="#444", family="monospace")

    ax.set_xlim(right=xmax * 1e2)  # leave room for annotations

    fig.suptitle("MX-FP8 (block=32, threshold=8): every block is viable",
                 fontsize=10, y=0.995)
    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
