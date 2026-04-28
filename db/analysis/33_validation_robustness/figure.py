#!/usr/bin/env python3
"""Validation §3 — per-bench spread of edge cases.

Allocation-size span per bench on a log-x axis: a horizontal whisker from
min_size to max_size with a marker at median_size. Order: ascending
median size. Tells reviewers we're not testing on a narrow size band.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv").sort_values("median_size")

    fig, ax = plt.subplots(figsize=(8.0, 6.5))
    y = range(len(df))
    ax.hlines(y, df["min_size"].clip(lower=1), df["max_size"],
              color="#56B4E9", linewidth=2.5, alpha=0.7)
    ax.scatter(df["min_size"].clip(lower=1), y, marker="|", s=60,
               color="#0072B2", zorder=3)
    ax.scatter(df["max_size"], y, marker="|", s=60,
               color="#0072B2", zorder=3)
    ax.scatter(df["median_size"], y, marker="o", s=30,
               color="#D55E00", edgecolor="white", linewidth=0.5, zorder=4)

    ax.set_yticks(list(y))
    ax.set_yticklabels(df["bench"], fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("allocation size (bytes, log) — min / median / max")
    ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
