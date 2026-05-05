#!/usr/bin/env python3
"""Silent-store fraction per (bench, alloc_type).

Heatmap: rows are benches, columns are alloc_type (32bits / 64bits /
object). Cell color = fraction of stores whose value matches the most
recent prior write to the same (alloc_addr, generation, offset) — the
upper bound on what silent-store elimination could remove. Cells are
annotated with the percentage; missing (bench, alloc_type) combos are
left blank.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

ALLOC_TYPES = ["32bits", "64bits", "object"]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    M = (df.pivot(index="bench", columns="alloc_type", values="silent_frac")
           .reindex(columns=ALLOC_TYPES)
           .sort_index())
    arr = M.to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(4.6, max(4.0, 0.22 * len(M) + 1.5)))
    cmap = LinearSegmentedColormap.from_list(
        "soft_rdylgn", ["#f4a582", "#ffffbf", "#91cf60"]
    )
    im = ax.imshow(arr, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(ALLOC_TYPES)))
    ax.set_xticklabels(ALLOC_TYPES, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(M)))
    ax.set_yticklabels(M.index.tolist(), fontsize=8)

    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            v = arr[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                    fontsize=7, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    cbar.set_label("% silent stores", fontsize=9)
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
