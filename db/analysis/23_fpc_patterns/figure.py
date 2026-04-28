#!/usr/bin/env python3
"""FPC pattern coverage per (bench, alloc_type).

Heatmap of share of stores matching each FPC pattern (zero, sign-extended
{4,8,16,32}, high-zero-low16, repeating-byte). Last column is the OR-union
upper bound. Reads its sibling result.csv.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

COLS = [
    ("pct_zero",             "zero"),
    ("pct_sign4",            "sign-ext 4b"),
    ("pct_sign8",            "sign-ext 8b"),
    ("pct_sign16",           "sign-ext 16b"),
    ("pct_sign32",           "sign-ext 32b"),
    ("pct_high_zero_low16",  "hi=0 lo16"),
    ("pct_repeating_byte",   "rep byte"),
    ("pct_any_pattern",      "any (∪)"),
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df["row"] = df["bench"] + " · " + df["alloc_type"]
    df = df.sort_values("row")

    M = df[[c for c, _ in COLS]].fillna(0).to_numpy()

    fig, ax = plt.subplots(figsize=(8.5, max(4.0, 0.18 * len(df) + 1.5)))
    im = ax.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=1)

    ax.set_xticks(range(len(COLS)))
    ax.set_xticklabels([n for _, n in COLS], rotation=30, ha="right",
                       fontsize=8)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["row"].tolist(), fontsize=7)

    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            color = "white" if v < 0.55 else "black"
            ax.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                    fontsize=6, color=color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("share of stores", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
