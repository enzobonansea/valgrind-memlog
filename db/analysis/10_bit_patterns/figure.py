#!/usr/bin/env python3
"""Bit-pattern shares per (bench, alloc_type).

Per row, four overlapping shares: exact-zero values, biased-exponent-zero
values, mantissa-zero values, and pairs whose adjacent (within the same
buffer) store wrote the same bits. The four categories overlap by
construction — a value of 0 satisfies all three pattern tests. The right
margin annotates the mean Hamming distance to the previous store within
the same buffer (lower → more spatially coherent).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

# Wong-palette categories (colorblind-safe).
CATS = [
    ("zero_values",   "value = 0",          "#0072B2", "total"),
    ("exp_zero",      "exponent = 0",       "#56B4E9", "total"),
    ("mantissa_zero", "mantissa = 0",       "#E69F00", "total"),
    ("bit_identical", "= prev (same buf)",  "#009E73", "pairs"),
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df = df.sort_values(["alloc_type", "bench"]).reset_index(drop=True)

    fig, axes = plt.subplots(
        1, 2, figsize=(11.5, 6.0), sharex=True,
        gridspec_kw={"wspace": 0.45},
    )

    for ax, atype in zip(axes, ("32bits", "64bits")):
        sub = df[df.alloc_type == atype].reset_index(drop=True)
        n = len(sub)
        y = np.arange(n)
        h = 0.20  # bar height

        for k, (col, label, color, denom_col) in enumerate(CATS):
            denom = sub[denom_col].replace(0, np.nan)
            frac = (sub[col] / denom).to_numpy(dtype=float)
            ax.barh(y - 1.5 * h + k * h, frac,
                    height=h, color=color, edgecolor="white",
                    linewidth=0.4, alpha=0.95, label=label)

        ax.set_yticks(y)
        ax.set_yticklabels(sub["bench"].tolist(), fontsize=7)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.0)
        ax.set_xlabel("share of stores (or pairs)", fontsize=9)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_title(atype, fontsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        # Right-margin Hamming annotation per row.
        max_h = 64 if atype == "64bits" else 32
        for i, r in sub.iterrows():
            mh = r["mean_hamming"]
            if pd.isna(mh):
                txt = "—"
            else:
                txt = f"H={mh:4.1f}/{max_h}"
            ax.text(1.02, i, txt, ha="left", va="center",
                    fontsize=6.5, color="#444",
                    family="monospace",
                    transform=ax.get_yaxis_transform())

    axes[0].legend(loc="lower left", bbox_to_anchor=(0.0, 1.04),
                   ncol=4, fontsize=7.5, frameon=False, handlelength=1.4,
                   columnspacing=1.4)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
