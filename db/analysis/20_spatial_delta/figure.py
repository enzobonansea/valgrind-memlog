#!/usr/bin/env python3
"""Spatial delta-coverage between physically-adjacent offsets in the snapshot.

For each (bench, alloc_type) pair the query records nested coverage
fractions: bit-identical ⊂ Hamming ≤ 8 ⊂ Hamming ≤ 16 ⊂ residual. The
figure renders these as a four-segment stacked bar per row, with mean
Hamming and mean log-delta annotated in the right margin. Direct
measurement of how much spatial value similarity a delta encoder could
exploit on the bench's final-state snapshot.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

SEGMENTS = [
    ("bit-identical",   "#1a9850"),  # darkest green: most compressible
    ("Hamming ≤ 8",     "#91cf60"),
    ("Hamming ≤ 16",    "#fee08b"),
    ("residual",        "#fc8d59"),  # orange: needs full word
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df["row"] = df["bench"] + " · " + df["alloc_type"]
    df = df.sort_values(["bench", "alloc_type"]).reset_index(drop=True)

    pairs = df["pairs"].astype(float).replace(0, np.nan)
    f_id = (df["bit_identical"] / pairs).fillna(0.0)
    f_8  = ((df["delta_le_8b"]  - df["bit_identical"]) / pairs).fillna(0.0)
    f_16 = ((df["delta_le_16b"] - df["delta_le_8b"])   / pairs).fillna(0.0)
    f_rest = (1.0 - (f_id + f_8 + f_16)).clip(lower=0.0)

    fracs = np.column_stack([f_id, f_8, f_16, f_rest])

    n = len(df)
    fig, ax = plt.subplots(figsize=(11.0, max(4.5, 0.22 * n + 1.5)))
    y = np.arange(n)

    left = np.zeros(n)
    for k, (label, color) in enumerate(SEGMENTS):
        ax.barh(y, fracs[:, k], left=left,
                color=color, edgecolor="white", linewidth=0.4,
                height=0.78, label=label)
        left = left + fracs[:, k]

    ax.set_yticks(y)
    ax.set_yticklabels(df["row"].tolist(), fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("share of adjacent-offset pairs (snapshot)", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Right-margin annotations: mean Hamming and mean log-delta.
    for i, r in df.iterrows():
        h = r["mean_hamming"]
        ld = r["mean_log_delta"]
        max_h = 64 if r["alloc_type"] == "64bits" else 32
        txt = f"H={h:5.2f}/{max_h}  log₂Δ={ld:5.2f}"
        ax.text(1.02, i, txt, ha="left", va="center",
                fontsize=6.5, color="#444", family="monospace",
                transform=ax.get_yaxis_transform())

    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02),
              ncol=4, fontsize=7.5, frameon=False, handlelength=1.4)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
