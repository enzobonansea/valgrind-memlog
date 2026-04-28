#!/usr/bin/env python3
"""Validation §3 — testing volume per benchmark.

Three small horizontal bars (log-x) per bench: total stores, distinct
buffers, distinct call sites. Same bench order on all three so the user
can scan correlations.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

COLS = [
    ("stores",      "stores"),
    ("buffers",     "distinct buffers"),
    ("call_sites",  "distinct call sites"),
]
COLORS = ["#0072B2", "#E69F00", "#CC79A7"]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv").sort_values("stores")

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 7.0), sharey=True)
    for ax, (col, label), color in zip(axes, COLS, COLORS):
        ax.barh(range(len(df)), df[col].clip(lower=1), color=color,
                edgecolor="white", linewidth=0.4)
        ax.set_yticks(range(len(df)))
        ax.set_yticklabels(df["bench"], fontsize=8)
        ax.set_xscale("log")
        ax.set_xlabel(label + " (log)")
        ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
