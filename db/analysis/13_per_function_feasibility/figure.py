#!/usr/bin/env python3
"""Per-function reduced-precision feasibility (companion to Q12).

Heatmap of format-feasibility shares for the hottest allocation sites.
Same color scale and column order as 12_format_feasibility, so the two
figures read as a pair: Q12 = per (bench, alloc_type), Q13 = per
(bench, alloc_type, site). Each row is "bench · alloc_type · site",
sorted by bench then store volume; only the top 5 sites per bench are
shown so the figure stays legible.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

FORMATS = [
    ("pct_fp8_e4m3", "FP8 E4M3"),
    ("pct_fp8_e5m2", "FP8 E5M2"),
    ("pct_bf16",     "bfloat16"),
    ("pct_fp16",     "FP16"),
    ("pct_fp32",     "FP32"),
]

TOP_PER_BENCH = 5


def truncate(s: str, n: int = 36) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df = (df.sort_values(["bench", "total"], ascending=[True, False])
            .groupby("bench", group_keys=False)
            .head(TOP_PER_BENCH)
            .reset_index(drop=True))
    df["row"] = (df["bench"] + " · " + df["alloc_type"]
                 + " · " + df["site"].map(truncate))

    cols = [c for c, _ in FORMATS]
    M = df[cols].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(8.2, max(4.0, 0.20 * len(df) + 1.5)))
    cmap = LinearSegmentedColormap.from_list(
        "soft_rdylgn", ["#f4a582", "#ffffbf", "#91cf60"]
    )
    masked = np.ma.masked_invalid(M)
    cmap.set_bad(color="#e6e6e6")
    im = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=0, vmax=1)

    ax.set_xticks(range(len(FORMATS)))
    ax.set_xticklabels([n for _, n in FORMATS], rotation=30, ha="right",
                       fontsize=9)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["row"].tolist(), fontsize=6.5,
                       family="monospace")

    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v):
                ax.text(j, i, "—", ha="center", va="center",
                        fontsize=6, color="#888888")
                continue
            ax.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                    fontsize=6, color="black")

    # Faint horizontal separators between benches.
    bench_changes = np.where(df["bench"].values[1:] != df["bench"].values[:-1])[0]
    for k in bench_changes:
        ax.axhline(k + 0.5, color="white", lw=1.2)

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("% of stores losslessly representable", fontsize=9)
    cbar.set_ticks(np.linspace(0, 1, 6))
    cbar.set_ticklabels([f"{int(t*100)}" for t in np.linspace(0, 1, 6)])
    cbar.ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
