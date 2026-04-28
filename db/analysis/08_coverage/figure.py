#!/usr/bin/env python3
"""Figure 8 — write density per (bench, alloc_type).

Two panels (32-bit slots, 64-bit slots). x = avg slot coverage (fraction of
slots written, linear 0..1). y = avg writes per written slot (log). Bubble
area scales with the number of allocations.

Quadrants name the regime each bench operates in:
  - sparse poking      (low coverage, low writes/slot)
  - rewrite churn      (low coverage, many writes/slot)
  - streaming / init   (high coverage, low writes/slot)
  - in-place update    (high coverage, many writes/slot)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "figure.svg"

PANEL_COLOR = {"32bits": "#56B4E9", "64bits": "#0072B2"}
COV_SPLIT = 0.5
WPS_SPLIT = 10.0
WPS_LO, WPS_HI = 0.9, 1.0e4

QUADRANTS = [
    (0.02, WPS_LO * 1.4, "sparse poking",     "left",  "bottom"),
    (0.02, WPS_HI * 0.7, "rewrite churn",     "left",  "top"),
    (0.98, WPS_LO * 1.4, "streaming / init",  "right", "bottom"),
    (0.98, WPS_HI * 0.7, "in-place update",   "right", "top"),
]


def draw_panel(ax, sub: pd.DataFrame, atype: str) -> None:
    ax.axhspan(WPS_SPLIT, WPS_HI, xmin=0.0, xmax=COV_SPLIT,
               color="#d62728", alpha=0.05, zorder=0)
    ax.axhspan(WPS_LO, WPS_SPLIT, xmin=COV_SPLIT, xmax=1.0,
               color="#2ca02c", alpha=0.05, zorder=0)
    ax.axhspan(WPS_SPLIT, WPS_HI, xmin=COV_SPLIT, xmax=1.0,
               color="#ff7f0e", alpha=0.07, zorder=0)
    ax.axvline(COV_SPLIT, color="#888", linewidth=0.6, linestyle="--", zorder=1)
    ax.axhline(WPS_SPLIT, color="#888", linewidth=0.6, linestyle="--", zorder=1)

    for x, y, txt, ha, va in QUADRANTS:
        ax.text(x, y, txt, ha=ha, va=va, fontsize=8,
                color="#555", style="italic", zorder=1)

    sub = sub.sort_values("allocations", ascending=False)
    sizes = np.log10(sub["allocations"].clip(lower=1)) * 45.0 + 25.0
    y = sub["avg_writes_per_slot"].clip(lower=WPS_LO * 1.05)
    ax.scatter(sub["avg_coverage"], y,
               s=sizes, color=PANEL_COLOR[atype], alpha=0.65,
               edgecolor="white", linewidth=0.6, zorder=3)

    for _, row in sub.iterrows():
        ax.annotate(row["bench"],
                    (row["avg_coverage"],
                     max(row["avg_writes_per_slot"], WPS_LO * 1.05)),
                    fontsize=7, alpha=0.85,
                    xytext=(5, 3), textcoords="offset points",
                    zorder=4)

    ax.set_xlim(-0.03, 1.06)
    ax.set_ylim(WPS_LO, WPS_HI)
    ax.set_yscale("log")
    ax.set_xlabel("avg coverage (fraction of slots written)")
    ax.set_title(f"{atype} ({len(sub)} benches, "
                 f"{int(sub['allocations'].sum()):,} allocations)",
                 fontsize=10)
    ax.grid(which="both", linestyle=":", alpha=0.35, zorder=1)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df = df.dropna(subset=["avg_coverage", "avg_writes_per_slot"])

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.6), sharey=True)
    for ax, atype in zip(axes, ("32bits", "64bits")):
        draw_panel(ax, df[df.alloc_type == atype], atype)
    axes[0].set_ylabel("avg writes per written slot (log)")

    handles = [
        plt.scatter([], [], s=np.log10(n) * 45.0 + 25.0,
                    color="#888888", alpha=0.65,
                    edgecolor="white", linewidth=0.6,
                    label=f"{n:,}")
        for n in (1, 100, 10_000)
    ]
    axes[1].legend(handles=handles, title="# allocations",
                   loc="lower right", frameon=False, fontsize=8,
                   labelspacing=1.4, borderpad=0.8)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
