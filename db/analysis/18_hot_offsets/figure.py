#!/usr/bin/env python3
"""Hot-offset concentration within each bench's heaviest buffers.

For every bench the query keeps the 10 buffers with the most stores and,
within each, the 5 most-written offsets. Each dot below is one of those
(buffer, offset) rows. x = the offset's share of *its buffer*'s writes;
dot size = the offset's share of the *bench*'s total writes; colour =
within-bench buffer rank (1 = hottest buffer). Wide horizontal spread
means the hot buffers concentrate writes on a few offsets; dots clumped
near 0% mean the buffer's writes are spread evenly.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")

    # Buffer rank within bench: 1 = heaviest buffer (top of CSV per bench).
    buffer_id = (df.groupby("bench")[["addr", "generation"]]
                   .apply(lambda g: g.assign(
                       _rank=(g["addr"].astype(str) + "/"
                              + g["generation"].astype(str))
                                .rank(method="dense").astype(int)))
                   .reset_index(drop=True))
    df["buffer_rank"] = buffer_id["_rank"]

    benches = sorted(df["bench"].unique())
    n = len(benches)
    y_of = {b: i for i, b in enumerate(benches)}
    df["y"] = df["bench"].map(y_of)

    fig, ax = plt.subplots(figsize=(9.5, max(4.0, 0.35 * n + 1.0)))

    cmap = plt.get_cmap("viridis")
    max_rank = int(df["buffer_rank"].max())
    colors = df["buffer_rank"].map(
        lambda r: cmap(0.85 - 0.7 * (r - 1) / max(1, max_rank - 1)))

    # Marker area scales with pct_of_bench (heavy contributors look bigger).
    pob = df["pct_of_bench"].fillna(0.0).clip(lower=0.0)
    sizes = 6 + 90 * np.sqrt(pob / max(pob.max(), 1e-9))

    # Small vertical jitter so co-incident dots don't fully overlap.
    rng = np.random.default_rng(seed=0)
    jitter = rng.uniform(-0.18, 0.18, size=len(df))

    ax.scatter(df["pct_of_buffer"], df["y"] + jitter,
               s=sizes, c=colors, alpha=0.75,
               edgecolor="white", linewidth=0.3, zorder=2)

    # Per-bench, label the single hottest (buffer 1, offset 1) dot with the
    # offset value, but only if it dominates (>=5% of buffer).
    rank1 = df[df["buffer_rank"] == 1].copy()
    rank1["off_rnk"] = (rank1.groupby("bench")["writes"]
                              .rank(method="first", ascending=False))
    top = rank1[rank1["off_rnk"] == 1]
    for _, r in top.iterrows():
        if r["pct_of_buffer"] >= 5.0:
            ax.text(r["pct_of_buffer"] + 1.5, y_of[r["bench"]],
                    f"@{int(r['offset'])}",
                    ha="left", va="center", fontsize=6,
                    color="#444", family="monospace")

    ax.set_yticks(range(n))
    ax.set_yticklabels(benches, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(-1.5, 102)
    ax.set_xlabel("offset's share of its buffer's writes (%)", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Reverse-coloured colourbar so 1 = darkest at top.
    sm = plt.cm.ScalarMappable(
        cmap=cmap.reversed(),
        norm=plt.Normalize(vmin=1, vmax=max_rank))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("buffer rank within bench", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
