#!/usr/bin/env python3
"""wrf silent-store zoom: the heaviest individual buffers, one row each.

Companion to 35_per_buffer_silent (the whole-suite strip). That figure
compresses wrf into a single row of dots; this one names the buffers.
Each row is one buffer -- one (alloc_addr, generation), labelled
<addr>_<generation> -- and the dot sits at its silent-store fraction,
area log-scaled in silent-eligible pairs. Rows are the top N buffers by
pairs, sorted by silent fraction so the spread is visible top to bottom;
the right margin names the allocating function, so buffers from the same
source-level site line up. The dashed line marks wrf's benchmark
aggregate -- the single number Figure~2 reports for the whole row. The
point: the heavy buffers of one benchmark span the full 0-to-1 range and
almost none sit at the aggregate.
"""
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "figure.svg"

TOP_BUFFERS = 22
COLORS = {"32bits": "#0072B2", "64bits": "#56B4E9", "object": "#009E73"}
SIZE_LO, SIZE_HI = 3.0, 9.0
AREA_LO, AREA_HI = 20.0, 320.0


def dot_area(pairs: np.ndarray) -> np.ndarray:
    return np.interp(np.log10(pairs.astype(float)),
                     [SIZE_LO, SIZE_HI], [AREA_LO, AREA_HI])


def short(site: str) -> str:
    r"""Drop the Fortran module prefix (...\_MOD\_) for a readable label."""
    s = re.sub(r'^.*_MOD_', '', str(site))
    return s or "(unattributed)"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df = df[df.pairs > 0].copy()

    agg = df["silent"].sum() / df["pairs"].sum()   # wrf benchmark aggregate

    buf = df.sort_values("pairs", ascending=False).head(TOP_BUFFERS).copy()
    buf = buf.sort_values("silent_frac", ascending=False).reset_index(drop=True)
    buf["label"] = buf["addr"] + "_" + buf["generation"].astype(str)
    y = np.arange(len(buf))

    fig, ax = plt.subplots(figsize=(8.6, 0.34 * len(buf) + 1.7))
    for i in range(0, len(buf), 2):
        ax.axhspan(i - 0.5, i + 0.5, color="#000000", alpha=0.045, zorder=0)

    # Stem from the aggregate to each buffer, so the deviation is legible.
    ax.hlines(y, agg, buf["silent_frac"], color="#BBBBBB",
              linewidth=0.9, zorder=1)
    for atype, color in COLORS.items():
        sub = buf[buf.alloc_type == atype]
        if sub.empty:
            continue
        ax.scatter(sub["silent_frac"], sub.index,
                   s=dot_area(sub["pairs"].to_numpy()), color=color,
                   alpha=0.75, edgecolor="white", linewidth=0.5,
                   label=atype, zorder=3)

    ax.axvline(agg, color="#000000", linestyle="--", linewidth=1.4, zorder=2)
    ax.text(agg + 0.01, len(buf) - 0.7, f"wrf aggregate {agg:.0%}",
            rotation=90, ha="left", va="bottom", fontsize=9.0,
            color="#000000", zorder=5)

    # Right margin: the allocating function for each buffer.
    for i, row in buf.iterrows():
        ax.text(1.02, i, short(row["site"]), ha="left", va="center",
                fontsize=8.0, color="#555", family="monospace",
                transform=ax.get_yaxis_transform())
    ax.text(1.02, -0.012, "allocating\nfunction", ha="left", va="top",
            fontsize=8.5, color="#555", style="italic",
            transform=ax.transAxes)

    ax.set_yticks(y)
    ax.set_yticklabels(buf["label"], fontsize=9.0, family="monospace")
    ax.set_ylim(len(buf) - 0.5, -0.5)
    ax.set_xlim(-0.015, 1.015)
    ax.set_xlabel("per-buffer silent-store fraction", fontsize=12)
    ax.set_ylabel("buffer  (address_generation)", fontsize=11)
    ax.tick_params(axis="x", labelsize=10)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    size_key = [plt.scatter([], [], s=dot_area(np.array([10.0**e])),
                            color="#888", alpha=0.75, edgecolor="white",
                            linewidth=0.5) for e in (5, 7, 9)]
    handles, labels = ax.get_legend_handles_labels()
    handles += size_key
    labels += [r"$10^5$ pairs", r"$10^7$", r"$10^9$"]
    ax.legend(handles, labels, loc="lower left", frameon=False,
              bbox_to_anchor=(0.0, 1.005), ncol=6, fontsize=9.5,
              columnspacing=0.9, handletextpad=0.35, borderaxespad=0.0)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}  (aggregate {agg:.3f})")


if __name__ == "__main__":
    main()
