#!/usr/bin/env python3
"""Per-(site, offset) IEEE exponent stability — scaling-granularity story.

For each top allocation site, two facts decide whether per-tensor or
per-channel scaling is enough:
  - `frac_constant_exp` — share of offsets whose unbiased exponent never
    changed across the run. High = per-channel scaling is exact.
  - `mean_exp_range`   — mean (max − min) exponent per offset. High =
    only per-token scaling (recompute scale every store) is safe.

Layout: scatter — x = mean_exp_range (log), y = frac_constant_exp,
marker size = log distinct_offsets, colour = bench. The top-left corner
("low spread + high constant share") is the per-channel-friendly region;
the bottom-right corner is per-token territory.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def _size(offsets):
    return 18 + 35 * np.log10(np.clip(offsets, 1, None))


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    benches = sorted(df["bench"].unique())
    cmap = plt.get_cmap("turbo")
    bcol = {b: cmap(i / max(1, len(benches) - 1)) for i, b in enumerate(benches)}

    fig, ax = plt.subplots(figsize=(9.5, 6.5))

    # Region guides — soft shading for the per-channel sweet spot
    # (low spread, high frac_constant) and the per-token region.
    ax.axhspan(0.8, 1.05, color="#009E73", alpha=0.05, zorder=0)
    ax.axhspan(0.0, 0.2, color="#D55E00", alpha=0.05, zorder=0)
    ax.text(0.015, 0.97, "per-channel scaling exact",
            transform=ax.transAxes,
            fontsize=8, color="#009E73", ha="left", va="top")
    ax.text(0.985, 0.03, "per-token scaling required",
            transform=ax.transAxes,
            fontsize=8, color="#D55E00", ha="right", va="bottom")

    for bench in benches:
        sub = df[df.bench == bench]
        ax.scatter(
            sub["mean_exp_range"].clip(lower=0.05),
            sub["frac_constant_exp"],
            s=_size(sub["distinct_offsets"]),
            color=bcol[bench], edgecolor="white", linewidth=0.5,
            alpha=0.85, label=bench,
        )

    ax.set_xscale("log")
    ax.set_xlim(0.04, max(2000, df["mean_exp_range"].max() * 1.2))
    ax.set_ylim(-0.02, 1.03)
    ax.set_xlabel("mean per-offset exponent range (max − min, log)")
    ax.set_ylabel("fraction of offsets with constant exponent")
    ax.grid(linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    bench_handles = [plt.Line2D([0], [0], marker="o", color="w",
                                markerfacecolor=bcol[b], markersize=6,
                                markeredgecolor="white", label=b)
                     for b in benches]
    bench_legend = ax.legend(handles=bench_handles, loc="center left",
                             bbox_to_anchor=(1.02, 0.5),
                             frameon=False, fontsize=7,
                             title="bench", title_fontsize=7)
    ax.add_artist(bench_legend)

    size_handles = [
        plt.scatter([], [], s=_size(v), color="#888",
                    edgecolor="white", linewidth=0.4, alpha=0.7,
                    label=f"{v:,}")
        for v in (1_000, 1_000_000, 10_000_000)
    ]
    ax.legend(handles=size_handles, loc="lower left", frameon=False,
              fontsize=7, title="distinct offsets", title_fontsize=7,
              labelspacing=1.2, borderpad=0.8)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
