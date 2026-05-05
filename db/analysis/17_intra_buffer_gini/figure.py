#!/usr/bin/env python3
"""Intra-buffer write-concentration via the Gini coefficient.

Per (bench, alloc_type), the query reports min / median / mean / max
Gini across all buffers in that group, plus a write-weighted mean
(buffers count proportionally to their store volume). G = 0 means
writes are uniform across touched offsets; G → 1 means writes pile
onto a single hot offset.

Each row shows a [min, max] range bar (clipped to [0, 1] — see note),
with median (line tick), mean (filled dot) and write-weighted mean
(open ring) overlaid. Big gaps between unweighted and write-weighted
mean signal that a few hot buffers carry disproportionate traffic.

Note: the xz row has overflow-corrupted max/mean values (G should be
in [0, 1]); they're clipped to 1.0 for plotting and flagged in the
margin so the rest of the figure remains readable.
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

    # Detect rows with out-of-range values (numerical overflow); clip for
    # plotting, flag in the margin.
    cols = ["mean_gini", "median_gini", "min_gini", "max_gini",
            "write_weighted_gini"]
    flagged = (df[cols] > 1.0).any(axis=1) | (df[cols] < 0.0).any(axis=1)
    clipped = df.copy()
    for c in cols:
        clipped[c] = clipped[c].clip(lower=0.0, upper=1.0)

    n = len(clipped)
    fig, ax = plt.subplots(figsize=(8.0, max(4.5, 0.22 * n + 1.5)))
    y = np.arange(n)

    # Min/max range bar.
    ax.hlines(y, clipped["min_gini"], clipped["max_gini"],
              color="#bdbdbd", lw=2.0, alpha=0.9, zorder=1)
    # Endpoint ticks.
    ax.plot(clipped["min_gini"], y, "|", color="#9e9e9e", ms=6, mew=1.0)
    ax.plot(clipped["max_gini"], y, "|", color="#9e9e9e", ms=6, mew=1.0)
    # Median (small tick).
    ax.plot(clipped["median_gini"], y, "|", color="#1a365d",
            ms=10, mew=1.4, zorder=3, label="median")
    # Mean (filled dot).
    ax.plot(clipped["mean_gini"], y, "o", color="#2b6cb0",
            ms=4.5, mec="white", mew=0.6, zorder=4, label="mean")
    # Write-weighted mean (open ring).
    ax.plot(clipped["write_weighted_gini"], y, "o", mfc="none",
            mec="#d55e00", mew=1.2, ms=6, zorder=5,
            label="write-weighted mean")

    ax.set_yticks(y)
    ax.set_yticklabels(clipped["row"].tolist(), fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("Gini coefficient (0 = uniform, 1 = single hot offset)",
                  fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", lw=0.3, alpha=0.3)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Buffer count + overflow flag in the right margin.
    for i, r in clipped.iterrows():
        suffix = "  ⚠ overflow" if flagged.iloc[i] else ""
        ax.text(1.03, i, f"n={int(r['buffers'])}{suffix}",
                ha="left", va="center", fontsize=6.5,
                color="#444", family="monospace",
                transform=ax.get_yaxis_transform())

    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02),
              ncol=3, fontsize=7, frameon=False, handlelength=1.5)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
