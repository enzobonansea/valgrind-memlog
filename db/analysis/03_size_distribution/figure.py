#!/usr/bin/env python3
"""Figure 4 — allocation-size landscape per bench.

Log-log CCDF: x = allocation size (bytes, log), y = number of allocations
at that size or larger (log). One line per bench. Tail behavior shows how
heavy-tailed the size distribution is in each workload.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")

    # CCDF per bench: P(size >= x) on a count basis, sorted ascending in size.
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    cmap = plt.get_cmap("turbo")
    benches = sorted(df["bench"].unique(),
                     key=lambda b: -df.loc[df.bench == b, "allocations"].sum())
    for i, bench in enumerate(benches):
        sub = (df[df.bench == bench]
               .sort_values("size_bucket_bytes"))
        if sub.empty:
            continue
        # CCDF: cumulative sum from largest size down.
        sub = sub.sort_values("size_bucket_bytes", ascending=False)
        sub["ccdf"] = sub["allocations"].cumsum()
        sub = sub.sort_values("size_bucket_bytes")
        ax.plot(sub["size_bucket_bytes"], sub["ccdf"],
                marker="o", markersize=2.5, linewidth=1.0,
                color=cmap(i / max(1, len(benches) - 1)),
                label=bench, alpha=0.8)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("allocation size (bytes)")
    ax.set_ylabel("# allocations of size ≥ x")
    ax.grid(which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=7, ncol=1, title="bench")
    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
