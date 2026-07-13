#!/usr/bin/env python3
"""Lossless-representability per individual buffer, one strip per benchmark.

Three panels (FP8 E4M3 / bfloat16 / FP32). In each panel, one dot per
buffer at the fraction of its stores that are losslessly representable
in that format (mantissa trailing-zero criterion, thresholds as in
Q12); black tick = the benchmark's store-weighted aggregate, i.e. the
per-benchmark number the old per-(bench, alloc_type) heatmap reported.
Dot area grows with the buffer's store count (log scale); colour is
alloc_type. The FP32 panel plots only 64-bit buffers (32-bit values are
trivially representable). Same visual language as 35_per_buffer_silent.

Dots are the top MAX_DOTS buffers per bench with >= MIN_STORES stores;
the right margin (outer panel) reports plotted/total buffers and the
share of the bench's stores they carry.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

MIN_STORES = 1000
MAX_DOTS   = 400

COLORS = {"32bits": "#0072B2", "64bits": "#56B4E9"}

PANELS = [("pct_fp8_e4m3", "FP8 E4M3", False),
          ("pct_bf16",     "bfloat16", False),
          ("pct_fp32",     "FP32",     True)]   # True = 64-bit buffers only

SIZE_LO, SIZE_HI = 3.0, 9.0
AREA_LO, AREA_HI = 7.0, 120.0


def dot_area(n: np.ndarray) -> np.ndarray:
    return np.interp(np.log10(n.astype(float)),
                     [SIZE_LO, SIZE_HI], [AREA_LO, AREA_HI])


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")

    dots = (df.sort_values("total", ascending=False)
            .groupby("bench", group_keys=False)
            .apply(lambda g: (g[g["total"] >= MIN_STORES].head(MAX_DOTS)
                              if (g["total"] >= MIN_STORES).any() else g),
                   include_groups=True)
            .copy())
    kept = dots["total"].sum() / df["total"].sum()
    print(f"dots: {len(dots)}/{len(df)} buffers, {kept:.1%} of stores")

    # Row order: by bfloat16 store-weighted aggregate, highest on top.
    agg_bf16 = (df.assign(w=df.pct_bf16 * df.total)
                  .groupby("bench")
                  .apply(lambda g: g.w.sum() / g.total.sum(),
                         include_groups=False))
    benches = agg_bf16.sort_values(ascending=False).index.tolist()
    row_of = {b: i for i, b in enumerate(benches)}

    rng = np.random.default_rng(0)
    dots["y"] = (dots["bench"].map(row_of).astype(float)
                 + rng.uniform(-0.30, 0.30, len(dots)))

    fig, axes = plt.subplots(
        1, 3, figsize=(9.0, 0.33 * len(benches) + 1.6),
        sharey=True, gridspec_kw={"wspace": 0.08})

    for ax, (col, title, only64) in zip(axes, PANELS):
        sub_dots = dots[dots.alloc_type == "64bits"] if only64 else dots
        sub_all  = df[df.alloc_type == "64bits"] if only64 else df

        for i in range(0, len(benches), 2):
            ax.axhspan(i - 0.5, i + 0.5, color="#000000",
                       alpha=0.045, zorder=0)

        for atype, color in COLORS.items():
            s = sub_dots[sub_dots.alloc_type == atype]
            if s.empty:
                continue
            ax.scatter(s[col], s["y"], s=dot_area(s["total"].to_numpy()),
                       color=color, alpha=0.55,
                       edgecolor="white", linewidth=0.4,
                       label=atype, zorder=3)

        agg = (sub_all.assign(w=sub_all[col] * sub_all.total)
               .groupby("bench")
               .apply(lambda g: g.w.sum() / g.total.sum(),
                      include_groups=False)
               .reindex(benches))
        ax.scatter(agg.to_numpy(), np.arange(len(benches)),
                   marker="|", s=200, color="#000000", linewidth=1.7,
                   label="bench aggregate", zorder=4)

        ax.set_title(title, fontsize=12)
        ax.set_xlim(-0.03, 1.03)
        ax.set_xticks([0, 0.5, 1])
        ax.tick_params(axis="x", labelsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    axes[0].set_yticks(np.arange(len(benches)))
    axes[0].set_yticklabels(benches, fontsize=11)
    axes[0].set_ylim(len(benches) - 0.5, -0.5)
    fig.supxlabel("fraction of the buffer's stores losslessly representable",
                  fontsize=12, y=0.045)

    # Coverage annotation on the outer right margin.
    counts = dots.groupby("bench").size()
    totals = df.groupby("bench").size()
    cover  = (dots.groupby("bench")["total"].sum()
              / df.groupby("bench")["total"].sum())
    for b in benches:
        n, t = counts.get(b, 0), totals.get(b, 0)
        cell = f"{n}/{t:,}" if n < t else f"{t:,}"
        cov = cover.get(b, 0)
        cov = 0.0 if pd.isna(cov) else cov
        axes[2].text(1.06, row_of[b], f"{cell} · {cov:.0%}",
                     ha="left", va="center", fontsize=8.5, color="#555",
                     family="monospace",
                     transform=axes[2].get_yaxis_transform())
    axes[2].text(1.06, -0.012, "buffers ·\nstores shown",
                 ha="left", va="top", fontsize=8.5, color="#555",
                 style="italic", transform=axes[2].transAxes)

    size_key = [plt.scatter([], [], s=dot_area(np.array([10.0**e])),
                            color="#888", alpha=0.55, edgecolor="white",
                            linewidth=0.4)
                for e in (4, 6, 8)]
    handles, labels = axes[0].get_legend_handles_labels()
    handles += size_key
    labels  += [r"$10^4$ stores", r"$10^6$", r"$10^8$"]
    fig.legend(handles, labels, loc="upper center",
               bbox_to_anchor=(0.5, 1.0), frameon=False, ncol=6,
               fontsize=9.5, columnspacing=0.9, handletextpad=0.35)

    fig.tight_layout(rect=(0, 0.02, 1, 0.965))
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
