#!/usr/bin/env python3
"""Outlier-channel concentration — per-channel vs per-tensor scaling.

LLM-quantization papers (SmoothQuant, AWQ, LLM.int8(), QuIP#) hinge on
the empirical fact that outlier values cluster at a *small fixed set*
of offsets within each tensor. If that holds in our SPEC traces, a
per-channel scale (one scalar per offset) recovers the precision lost
to truncation; if outliers are uniformly distributed, the only safe
fallback is per-tensor scaling.

Q26 measures, per (bench, alloc_site, alloc_type), the share of
*distinct* offsets that ever carry a 99.9th-percentile outlier
(`channel_frac = outlier_offsets / distinct_offsets`).

Layout: scatter — x = distinct_offsets (log, buffer-size proxy),
y = channel_frac (0–1), marker size = log total stores, colour = bench.
The bottom band (channel_frac ≤ 0.05) is the per-channel-friendly
region; the top band (≥ 0.5) is per-tensor / mixed-precision territory.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def _size(total):
    return 18 + 30 * np.log10(np.clip(total, 1, None))


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    benches = sorted(df["bench"].unique())
    cmap = plt.get_cmap("turbo")
    bcol = {b: cmap(i / max(1, len(benches) - 1)) for i, b in enumerate(benches)}

    fig, ax = plt.subplots(figsize=(9.5, 6.5))

    # Region guides — green strip at the bottom (per-channel exact),
    # orange strip at the top (per-tensor / mixed-precision required).
    ax.axhspan(-0.02, 0.05, color="#009E73", alpha=0.06, zorder=0)
    ax.axhspan(0.5, 1.05, color="#D55E00", alpha=0.06, zorder=0)
    ax.text(0.015, 0.025, "per-channel scaling viable (≤5% offsets carry outliers)",
            transform=ax.transAxes,
            fontsize=8, color="#009E73", ha="left", va="bottom")
    ax.text(0.015, 0.97, "per-tensor / mixed-precision required",
            transform=ax.transAxes,
            fontsize=8, color="#D55E00", ha="left", va="top")

    for bench in benches:
        sub = df[df.bench == bench]
        ax.scatter(
            np.clip(sub["distinct_offsets"], 1, None),
            sub["channel_frac"],
            s=_size(sub["total"]),
            color=bcol[bench], edgecolor="white", linewidth=0.5,
            alpha=0.85, label=bench,
        )

    ax.set_xscale("log")
    ax.set_xlim(50, max(1e8, df["distinct_offsets"].max() * 1.2))
    ax.set_ylim(-0.04, 1.05)
    ax.set_xlabel("distinct offsets per site (log) — buffer size proxy")
    ax.set_ylabel("channel_frac = offsets carrying outliers / distinct offsets")
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
        for v in (1_000, 1_000_000, 100_000_000)
    ]
    ax.legend(handles=size_handles, loc="center right",
              bbox_to_anchor=(1.0, 0.35),
              frameon=False, fontsize=7,
              title="total stores", title_fontsize=7,
              labelspacing=1.4, borderpad=0.8)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
