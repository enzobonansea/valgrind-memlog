#!/usr/bin/env python3
"""BDI cache-line compressibility per (bench, alloc_type).

Heatmap: rows = (bench · alloc_type), columns = {single-slot lines,
BDI-8, BDI-16, BDI-32}. Cell colour = fraction of 64-byte lines that
fit in that delta-width (single-slot lines are trivially compressible).
The columns are nested by construction (BDI-8 ⊂ BDI-16 ⊂ BDI-32), so
reading left-to-right within a row tells the smallest delta width that
captures most of that row's lines.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

COLUMNS = [
    ("trivial",   "single-slot"),
    ("bdi8",      "BDI Δ ≤ 8 bits"),
    ("bdi16",     "BDI Δ ≤ 16 bits"),
    ("bdi32",     "BDI Δ ≤ 32 bits"),
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df["row"] = df["bench"] + " · " + df["alloc_type"]
    df = df.sort_values(["bench", "alloc_type"]).reset_index(drop=True)

    # Build the matrix. The bdiK_frac columns already use lines_with_>=2_slots
    # as the denominator; for the trivial column we report the all-lines share.
    M = np.column_stack([
        df["trivial_lines"] / df["lines"].replace(0, np.nan),
        df["bdi8_frac"],
        df["bdi16_frac"],
        df["bdi32_frac"],
    ]).astype(float)

    fig, ax = plt.subplots(figsize=(7.5, max(4.0, 0.20 * len(df) + 1.5)))
    cmap = LinearSegmentedColormap.from_list(
        "soft_rdylgn", ["#f4a582", "#ffffbf", "#91cf60"]
    )
    cmap.set_bad(color="#e6e6e6")
    masked = np.ma.masked_invalid(M)
    im = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(COLUMNS)))
    ax.set_xticklabels([n for _, n in COLUMNS], rotation=30, ha="right",
                       fontsize=9)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["row"].tolist(), fontsize=7)

    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v):
                ax.text(j, i, "—", ha="center", va="center",
                        fontsize=6, color="#888888")
                continue
            ax.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                    fontsize=6, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("% of 64-byte lines", fontsize=9)
    cbar.set_ticks(np.linspace(0, 1, 6))
    cbar.set_ticklabels([f"{int(t*100)}" for t in np.linspace(0, 1, 6)])
    cbar.ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
