#!/usr/bin/env python3
"""Per-bench allocation-site write profile.

For each bench, the query keeps the top-15 sites by store volume.
This figure stacks them per row so concentration shows up at a glance:
a single dark band on the left means one function dominates (e.g.
cactus' PUGH_EnableGArrayDataStorage at ~99%), while a quilt of bands
means traffic is spread across many sites (e.g. cam4, pop2, wrf).

Benches are ordered by their top-1 site's share, descending — so the
most concentrated benches sit at the top. The dominant site's name is
overlaid on its segment when it fits.

Each row's bar sums to 100% of *that bench's top-15 stores* (the query
already normalises within the displayed sites; for benches with a long
tail beyond rank 15, see Q11's write-concentration percentiles).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def truncate(s: str, n: int = 38) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df["rank"] = df.groupby("bench").cumcount()  # 0 = hottest

    # Order benches by top-1 share, descending.
    top1 = (df[df["rank"] == 0]
              .set_index("bench")["pct_of_bench"]
              .sort_values(ascending=False))
    bench_order = top1.index.tolist()

    n_benches = len(bench_order)
    fig, ax = plt.subplots(figsize=(9.5, max(4.0, 0.32 * n_benches + 1.0)))

    cmap = plt.get_cmap("viridis")
    max_rank = int(df["rank"].max())

    y_of = {b: i for i, b in enumerate(bench_order)}
    for bench in bench_order:
        sub = df[df["bench"] == bench].sort_values("rank")
        left = 0.0
        for _, r in sub.iterrows():
            w  = r["pct_of_bench"]
            rk = int(r["rank"])
            color = cmap(0.85 - 0.75 * (rk / max(1, max_rank)))
            ax.barh(y_of[bench], w, left=left,
                    color=color, edgecolor="white", linewidth=0.5,
                    height=0.78)
            # Label the dominant site if its segment is wide enough.
            if rk == 0 and w >= 8:
                ax.text(left + w / 2, y_of[bench],
                        truncate(str(r["site"]), 42),
                        ha="center", va="center", fontsize=6.5,
                        color="white", family="monospace")
            left += w

    ax.set_yticks(range(n_benches))
    ax.set_yticklabels(bench_order, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of bench's top-15 store volume", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Single colorbar-style legend explaining rank → color.
    sm = plt.cm.ScalarMappable(
        cmap=cmap.reversed(),
        norm=plt.Normalize(vmin=1, vmax=max_rank + 1),
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("site rank within bench (1 = hottest)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
