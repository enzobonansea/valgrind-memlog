#!/usr/bin/env python3
"""Required exponent bits per individual buffer, one strip per benchmark.

One dot per buffer at ceil(log2(max_e - min_e + 1)) — the minimum
exponent-bit width a format needs to span the buffer's observed dynamic
range. Buffers whose every store is zero sit at 0 bits (no exponent
needed). Vertical dashed lines mark the standard cutoffs: 4 bits =
FP8 E4M3, 5 = FP8 E5M2, 8 = bfloat16/FP32, 11 = FP64. A buffer left of
a cutoff is range-compatible with that format (window position must
still be checked — the paper joins this with the absolute [-6,8] etc.
windows). Black tick = store-weighted mean required bits. Same visual
language as Q35/Q36; dots are the top 400 buffers per bench by stores
(>= 1000 stores), coverage annotated in the right margin.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

MIN_STORES = 1000
MAX_DOTS   = 400

COLORS  = {"32bits": "#0072B2", "64bits": "#56B4E9"}
CUTOFFS = [(4, "E4M3"), (5, "E5M2"), (8, "bf16"), (11, "FP64")]

SIZE_LO, SIZE_HI = 3.0, 9.0
AREA_LO, AREA_HI = 8.0, 150.0


def dot_area(n: np.ndarray) -> np.ndarray:
    return np.interp(np.log10(n.astype(float)),
                     [SIZE_LO, SIZE_HI], [AREA_LO, AREA_HI])


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    span = (df["max_e"] - df["min_e"] + 1)
    df["req_bits"] = np.where(df["min_e"].isna(), 0.0,
                              np.ceil(np.log2(span.clip(lower=1))))

    dots = (df.sort_values("total", ascending=False)
            .groupby("bench", group_keys=False)
            .apply(lambda g: (g[g["total"] >= MIN_STORES].head(MAX_DOTS)
                              if (g["total"] >= MIN_STORES).any() else g),
                   include_groups=True)
            .copy())
    print(f"dots: {len(dots)}/{len(df)} buffers, "
          f"{dots.total.sum()/df.total.sum():.1%} of stores")

    agg = (df.assign(w=df.req_bits * df.total)
             .groupby("bench")
             .apply(lambda g: g.w.sum() / g.total.sum(),
                    include_groups=False))
    benches = agg.sort_values(ascending=False).index.tolist()
    row_of = {b: i for i, b in enumerate(benches)}

    rng = np.random.default_rng(0)
    dots["y"] = (dots["bench"].map(row_of).astype(float)
                 + rng.uniform(-0.30, 0.30, len(dots)))
    dots["x"] = dots["req_bits"] + rng.uniform(-0.28, 0.28, len(dots))

    fig, ax = plt.subplots(figsize=(8.0, 0.33 * len(benches) + 1.6))

    for i in range(0, len(benches), 2):
        ax.axhspan(i - 0.5, i + 0.5, color="#000000", alpha=0.045, zorder=0)
    for x, name in CUTOFFS:
        ax.axvline(x + 0.5, color="#999", lw=0.9, linestyle="--", zorder=1)
        ax.text(x + 0.5, -0.85, name, ha="center", va="bottom",
                fontsize=9, color="#555")

    for atype, color in COLORS.items():
        s = dots[dots.alloc_type == atype]
        ax.scatter(s["x"], s["y"], s=dot_area(s["total"].to_numpy()),
                   color=color, alpha=0.55,
                   edgecolor="white", linewidth=0.4,
                   label=atype, zorder=3)

    ax.scatter(agg.loc[benches].to_numpy(), np.arange(len(benches)),
               marker="|", s=230, color="#000000", linewidth=1.8,
               label="bench aggregate", zorder=4)

    counts = dots.groupby("bench").size()
    totals = df.groupby("bench").size()
    cover  = (dots.groupby("bench")["total"].sum()
              / df.groupby("bench")["total"].sum())
    for b in benches:
        n, t = counts.get(b, 0), totals.get(b, 0)
        cell = f"{n}/{t:,}" if n < t else f"{t:,}"
        cov = cover.get(b, 0)
        cov = 0.0 if pd.isna(cov) else cov
        ax.text(1.015, row_of[b], f"{cell} · {cov:.0%}",
                ha="left", va="center", fontsize=8.5, color="#555",
                family="monospace",
                transform=ax.get_yaxis_transform())
    ax.text(1.015, -0.012, "buffers ·\nstores shown", ha="left", va="top",
            fontsize=8.5, color="#555", style="italic",
            transform=ax.transAxes)

    ax.set_yticks(np.arange(len(benches)))
    ax.set_yticklabels(benches, fontsize=11)
    ax.set_ylim(len(benches) - 0.5, -0.5)
    ax.set_xlim(-0.6, 11.6)
    ax.set_xticks(range(0, 12))
    ax.set_xlabel("required exponent bits "
                  r"($\lceil\log_2(\mathrm{max_e}-\mathrm{min_e}+1)\rceil$;"
                  " 0 = all-zero buffer)", fontsize=12)
    ax.tick_params(axis="x", labelsize=10)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    size_key = [plt.scatter([], [], s=dot_area(np.array([10.0**e])),
                            color="#888", alpha=0.55, edgecolor="white",
                            linewidth=0.4)
                for e in (4, 6, 8)]
    handles, labels = ax.get_legend_handles_labels()
    handles += size_key
    labels  += [r"$10^4$ stores", r"$10^6$", r"$10^8$"]
    fig.legend(handles, labels, loc="upper center",
               bbox_to_anchor=(0.5, 1.0), frameon=False, ncol=6,
               fontsize=9.5, columnspacing=0.9, handletextpad=0.35)

    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
