#!/usr/bin/env python3
"""Silent-store rate per individual buffer, one strip per benchmark.

Each dot is one buffer — one (alloc_addr, generation) — placed at its
silent-store fraction, vertically jittered within its benchmark's row.
Dot area grows with the buffer's number of silent-eligible pairs (log
scale), colour is the buffer's alloc_type (same Wong palette as the old
per-alloc-type figure). A black tick marks the benchmark's
volume-weighted aggregate — the single number the per-(bench,
alloc_type) view reports — so the spread the aggregate hides is visible
directly.

Buffers below MIN_PAIRS silent-eligible pairs are dropped from the
strip (their rate is noise); the aggregate tick is computed over ALL
buffers, dropped ones included.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

MIN_PAIRS = 1000  # noise floor for individual dots (same threshold as Q21)
MAX_DOTS  = 400   # per bench, top by pairs — cam4 alone has 22k+ buffers

# Wong-palette colour per alloc_type — matches 09_silent_stores panels.
COLORS = {"32bits": "#0072B2", "64bits": "#56B4E9", "object": "#009E73"}

# Dot area: log-scaled between these pair counts.
SIZE_LO, SIZE_HI = 3.0, 9.0     # log10(pairs) range mapped to area
AREA_LO, AREA_HI = 8.0, 150.0


def dot_area(pairs: np.ndarray) -> np.ndarray:
    lp = np.log10(pairs.astype(float))
    return np.interp(lp, [SIZE_LO, SIZE_HI], [AREA_LO, AREA_HI])


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")

    # Volume-weighted aggregate per bench over ALL buffers (matches Q09).
    agg = (df.groupby("bench")
             .apply(lambda g: g["silent"].sum() / g["pairs"].sum(),
                    include_groups=False)
             .rename("agg_frac"))

    # Top MAX_DOTS buffers per bench above the noise floor; a bench whose
    # every buffer is below MIN_PAIRS keeps all its buffers (a few noisy
    # dots beat an orphan aggregate tick).
    dots = (df.sort_values("pairs", ascending=False)
            .groupby("bench", group_keys=False)
            .apply(lambda g: (g[g["pairs"] >= MIN_PAIRS].head(MAX_DOTS)
                              if (g["pairs"] >= MIN_PAIRS).any() else g),
                   include_groups=True)
            .copy())
    kept = dots["pairs"].sum() / df["pairs"].sum()
    print(f"dots: {len(dots)}/{len(df)} buffers, "
          f"{kept:.1%} of all silent-eligible pairs")

    # Rows sorted by aggregate rate, highest on top.
    benches = agg.sort_values(ascending=False).index.tolist()
    row_of = {b: i for i, b in enumerate(benches)}

    rng = np.random.default_rng(0)
    dots["y"] = (dots["bench"].map(row_of).astype(float)
                 + rng.uniform(-0.30, 0.30, len(dots)))

    fig, ax = plt.subplots(figsize=(8.0, 0.33 * len(benches) + 1.6))

    # Alternate row shading so a row can be followed across the width.
    for i in range(0, len(benches), 2):
        ax.axhspan(i - 0.5, i + 0.5, color="#000000", alpha=0.045, zorder=0)

    for atype, color in COLORS.items():
        sub = dots[dots.alloc_type == atype]
        ax.scatter(sub["silent_frac"], sub["y"],
                   s=dot_area(sub["pairs"].to_numpy()),
                   color=color, alpha=0.55,
                   edgecolor="white", linewidth=0.4,
                   label=atype, zorder=3)

    # Benchmark aggregate tick (the old figure's single number per row).
    ax.scatter(agg.loc[benches].to_numpy(), np.arange(len(benches)),
               marker="|", s=230, color="#000000", linewidth=1.8,
               label="bench aggregate", zorder=4)

    # Right margin: plotted / total buffers and the share of the bench's
    # silent-eligible pairs the plotted dots carry (explicit truncation).
    counts   = dots.groupby("bench").size()
    totals   = df.groupby("bench").size()
    coverage = (dots.groupby("bench")["pairs"].sum()
                / df.groupby("bench")["pairs"].sum())
    for b in benches:
        n, t = counts.get(b, 0), totals.get(b, 0)
        cell = f"{n}/{t:,}" if n < t else f"{t:,}"
        cov  = coverage.get(b, 0)
        cov  = 0.0 if pd.isna(cov) else cov
        ax.text(1.015, row_of[b], f"{cell} · {cov:.0%}",
                ha="left", va="center", fontsize=8.5, color="#555",
                family="monospace",
                transform=ax.get_yaxis_transform())
    ax.text(1.015, -0.012, "buffers ·\npairs shown", ha="left", va="top",
            fontsize=8.5, color="#555", style="italic",
            transform=ax.transAxes)

    ax.set_yticks(np.arange(len(benches)))
    ax.set_yticklabels(benches, fontsize=11)
    ax.set_ylim(len(benches) - 0.5, -0.5)
    ax.set_xlim(-0.015, 1.015)
    ax.set_xlabel("per-buffer silent-store fraction", fontsize=12)
    ax.tick_params(axis="x", labelsize=10)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Size key: representative pair counts, drawn as legend entries.
    size_key = [plt.scatter([], [], s=dot_area(np.array([10.0**e])),
                            color="#888", alpha=0.55, edgecolor="white",
                            linewidth=0.4)
                for e in (4, 6, 8)]
    handles, labels = ax.get_legend_handles_labels()
    handles += size_key
    labels  += [r"$10^4$ pairs", r"$10^6$", r"$10^8$"]
    ax.legend(handles, labels, loc="lower left", frameon=False,
              bbox_to_anchor=(0.0, 1.005), ncol=7, fontsize=9.5,
              columnspacing=0.9, handletextpad=0.35, borderaxespad=0.0)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
