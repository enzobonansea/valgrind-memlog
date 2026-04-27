#!/usr/bin/env python3
"""Lossless-format feasibility per (bench, alloc_type).

Heatmap: rows are (bench, alloc_type), columns are FP8 E4M3 / FP8 E5M2 /
bfloat16 / FP16 / FP32. Cell color = fraction of stores losslessly
representable in that format (mantissa trailing-zero threshold). Reading
left-to-right within a row tells the story of how much precision a bench's
values actually need.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

FORMATS = [
    ("pct_fp8_e4m3", "FP8 E4M3"),
    ("pct_fp8_e5m2", "FP8 E5M2"),
    ("pct_bf16",     "bfloat16"),
    ("pct_fp16",     "FP16"),
    ("pct_fp32",     "FP32"),
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df["row"] = df["bench"] + " · " + df["alloc_type"]
    df = df.sort_values("row")

    cols = [c for c, _ in FORMATS]
    M = df[cols].fillna(0).to_numpy()

    fig, ax = plt.subplots(figsize=(7.5, max(4.0, 0.18 * len(df) + 1.5)))
    cmap = LinearSegmentedColormap.from_list(
        "soft_rdylgn", ["#f4a582", "#ffffbf", "#91cf60"]
    )
    im = ax.imshow(M, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(FORMATS)))
    ax.set_xticklabels([n for _, n in FORMATS], rotation=30, ha="right",
                       fontsize=9)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["row"].tolist(), fontsize=7)

    # Annotate each cell with its percentage.
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                    fontsize=6, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("% of stores losslessly representable", fontsize=9)
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
