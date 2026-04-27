#!/usr/bin/env python3
"""Exponent-range feasibility per (bench, alloc_type).

Left panel: horizontal range bars showing each row's [min_exp, max_exp]
span over normal-finite values, with FP8 E4M3 and E5M2 dynamic ranges
shaded as background bands and FP16 / bf16-FP32 / FP64 ranges marked
with reference lines. Mean exponent is shown as a dot.

Right panel: 2-column heatmap of the share of stores whose unbiased
exponent falls inside the FP8 E4M3 / E5M2 ranges (matches Q12's style
so the two figures read as a pair: Q12 = precision feasibility,
Q15 = range feasibility).

Rows where every value is zero / denormal / inf-NaN have no
normal-finite span, so the range bar is omitted and the heatmap cell
is 0 by construction.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

# Unbiased-exponent dynamic ranges for the formats we care about.
# Matches the bounds in query.sql.
E4M3 = (-9,    8)
E5M2 = (-16,   15)
FP16 = (-14,   15)
FP32 = (-126,  127)
FP64 = (-1022, 1023)

RANGE_COLS = [
    ("frac_in_e4m3_range", "E4M3"),
    ("frac_in_e5m2_range", "E5M2"),
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df["row"] = df["bench"] + " · " + df["alloc_type"]
    df = df.sort_values("row").reset_index(drop=True)

    n = len(df)
    fig = plt.figure(figsize=(9.0, max(4.5, 0.20 * n + 1.5)))
    gs  = fig.add_gridspec(1, 2, width_ratios=[3.2, 1.0], wspace=0.05)
    ax  = fig.add_subplot(gs[0, 0])
    axh = fig.add_subplot(gs[0, 1], sharey=ax)

    # ---- left: range bars over IEEE exponent axis -------------------
    # Background bands for FP8 E4M3 / E5M2.
    ax.axvspan(*E4M3, color="#91cf60", alpha=0.30, lw=0,
               label=f"FP8 E4M3 [{E4M3[0]}, {E4M3[1]}]")
    ax.axvspan(*E5M2, color="#fee08b", alpha=0.35, lw=0,
               label=f"FP8 E5M2 [{E5M2[0]}, {E5M2[1]}]")

    # Vertical reference lines for the wider formats.
    for lo, hi, name, color in [
        (*FP16, "FP16",          "#7f7f7f"),
        (*FP32, "bf16 / FP32",   "#404040"),
        (*FP64, "FP64",          "#202020"),
    ]:
        for x in (lo, hi):
            ax.axvline(x, color=color, lw=0.5, ls=":", alpha=0.7)

    ys = np.arange(n)
    for i, r in df.iterrows():
        lo, hi, mu = r["min_exp"], r["max_exp"], r["mean_exp"]
        if pd.isna(lo) or pd.isna(hi):
            ax.text(0, i, "no normal-finite values",
                    ha="center", va="center", fontsize=6,
                    color="#888888", style="italic")
            continue
        # Range bar.
        ax.hlines(i, lo, hi, color="#2b6cb0", lw=2.0, alpha=0.85)
        ax.plot([lo, hi], [i, i], "|", color="#2b6cb0", ms=6, mew=1.2)
        # Mean exponent.
        if not pd.isna(mu):
            ax.plot(mu, i, "o", color="#1a365d", ms=3.2, mec="white", mew=0.5)

    ax.set_yticks(ys)
    ax.set_yticklabels(df["row"].tolist(), fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(FP64[0] - 40, FP64[1] + 40)
    ax.set_xlabel("unbiased IEEE-754 exponent", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(axis="x", lw=0.3, alpha=0.3)

    # Legend (top of left panel).
    legend_handles = [
        Patch(facecolor="#91cf60", alpha=0.30, label="FP8 E4M3 range"),
        Patch(facecolor="#fee08b", alpha=0.35, label="FP8 E5M2 range"),
        plt.Line2D([0], [0], color="#2b6cb0", lw=2,
                   label="observed [min, max] exp (normal, finite)"),
        plt.Line2D([0], [0], marker="o", color="#1a365d", lw=0,
                   ms=3.2, label="mean exp"),
    ]
    ax.legend(handles=legend_handles, loc="lower left",
              bbox_to_anchor=(0.0, 1.02), ncol=2, fontsize=7,
              frameon=False, handlelength=1.5)

    # ---- right: in-range fraction heatmap ---------------------------
    cols = [c for c, _ in RANGE_COLS]
    M = df[cols].to_numpy(dtype=float)
    cmap = LinearSegmentedColormap.from_list(
        "soft_rdylgn", ["#f4a582", "#ffffbf", "#91cf60"]
    )
    im = axh.imshow(M, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    axh.set_xticks(range(len(RANGE_COLS)))
    axh.set_xticklabels([n for _, n in RANGE_COLS],
                        rotation=30, ha="right", fontsize=8)
    axh.tick_params(axis="y", left=False, labelleft=False)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            axh.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                     fontsize=6, color="black")
    for spine in ("top", "right", "left"):
        axh.spines[spine].set_visible(False)

    cbar = fig.colorbar(im, ax=axh, fraction=0.06, pad=0.08)
    cbar.set_label("% of stores in FP8 dynamic range", fontsize=8)
    cbar.set_ticks(np.linspace(0, 1, 6))
    cbar.set_ticklabels([f"{int(t*100)}" for t in np.linspace(0, 1, 6)])
    cbar.ax.tick_params(labelsize=7)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
