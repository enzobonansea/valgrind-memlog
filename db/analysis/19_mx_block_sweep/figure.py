#!/usr/bin/env python3
"""MX block-viability sweep across block sizes {8, 16, 32, 64, 128}.

`viable_spread4` and `viable_spread8` are uniformly 1.0 across every
(bench, alloc_type, block_size) triple — choice of block size does not
affect MX viability for this trace. The figure therefore plots the
*number of blocks* per block size (log y) so the volume scaling shows up,
with a header banner stating the headline result.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

BLOCK_SIZES = [8, 16, 32, 64, 128]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")

    # Sanity-print the headline so a future reader sees it in the runner log.
    flat4 = (df["viable_spread4"] == 1.0).all()
    flat8 = (df["viable_spread8"] == 1.0).all()
    print(f"viable_spread4 == 1.0 everywhere: {flat4}")
    print(f"viable_spread8 == 1.0 everywhere: {flat8}")

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 5.5),
                             sharex=True, sharey=True)

    for ax, atype in zip(axes, ("32bits", "64bits")):
        sub = df[df.alloc_type == atype]
        benches = sorted(sub["bench"].unique())
        cmap = plt.get_cmap("turbo")
        for i, bench in enumerate(benches):
            row = (sub[sub.bench == bench]
                       .sort_values("block_size"))
            ax.plot(row["block_size"], row["blocks"],
                    marker="o", markersize=3.5,
                    linewidth=1.0,
                    color=cmap(i / max(1, len(benches) - 1)),
                    alpha=0.85, label=bench)

        ax.set_title(atype, fontsize=10)
        ax.set_xlabel("block size", fontsize=9)
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks(BLOCK_SIZES)
        ax.set_xticklabels([str(b) for b in BLOCK_SIZES])
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(which="both", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    axes[0].set_ylabel("# blocks (log)", fontsize=9)
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=7, title="bench",
                    title_fontsize=7)

    fig.suptitle(
        "MX viability is flat at 100% across all block sizes  "
        "(spread ≤ 4 and spread ≤ 8 both hold for every block)",
        fontsize=10, y=0.99,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
