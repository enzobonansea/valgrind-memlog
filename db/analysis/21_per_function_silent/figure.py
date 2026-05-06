#!/usr/bin/env python3
"""Per-function silent-store rate vs per-function write volume.

Each dot is one allocation site (per bench, top-20 by `pairs`). x =
number of pair observations (log), y = silent fraction, colour = bench.
The bench-level aggregate from Q09 is a `pairs`-weighted average across
its dots — extremes near (high-x, high-y) are the cases where
function-grain silent-store elimination would be most lucrative.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

ANNOTATE_TOP_N = 12  # callouts


def truncate(s: str, n: int = 26) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df = df[df["pairs"] > 0].copy()

    benches = sorted(df["bench"].unique())
    cmap = plt.get_cmap("turbo")
    color_of = {b: cmap(i / max(1, len(benches) - 1))
                for i, b in enumerate(benches)}

    fig, ax = plt.subplots(figsize=(11.0, 6.0))

    # Marker size scales with `stores` so the heaviest sites pop visually.
    s_norm = np.sqrt(df["stores"] / df["stores"].max()) * 90 + 8

    for bench in benches:
        sub = df[df.bench == bench]
        ax.scatter(sub["pairs"], sub["silent_frac"],
                   s=np.sqrt(sub["stores"] / df["stores"].max()) * 90 + 8,
                   color=color_of[bench], alpha=0.78,
                   edgecolor="white", linewidth=0.4,
                   label=bench, zorder=3)
    _ = s_norm  # quieter linter

    # Callout the dozen most "interesting" sites: top by stores * silent_frac.
    df["score"] = df["stores"] * df["silent_frac"]
    callouts = df.sort_values("score", ascending=False).head(ANNOTATE_TOP_N)
    for _, r in callouts.iterrows():
        ax.annotate(
            f"{r['bench']} · {truncate(str(r['site']))}",
            xy=(r["pairs"], r["silent_frac"]),
            xytext=(8, 4), textcoords="offset points",
            fontsize=6.5, color="#222", family="monospace",
            arrowprops=dict(arrowstyle="-", color="#999", lw=0.5,
                            shrinkA=0, shrinkB=2),
        )

    ax.set_xscale("log")
    ax.set_xlabel("# pairs (stores with a previous write at the same offset, log)",
                  fontsize=9)
    ax.set_ylabel("silent fraction (silent / pairs)", fontsize=9)
    ax.set_ylim(-0.03, 1.03)
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Reference horizontal lines at 0.25 and 0.5.
    for thr in (0.25, 0.5, 0.75):
        ax.axhline(thr, color="#bbb", lw=0.5, linestyle="--", zorder=1)

    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=7, title="bench",
              title_fontsize=7, ncol=1)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
