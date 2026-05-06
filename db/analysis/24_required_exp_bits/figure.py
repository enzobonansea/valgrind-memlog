#!/usr/bin/env python3
"""Required exponent-bit-width per allocation site, weighted by stores.

Two-panel histogram (32-bit / 64-bit alignment): x = required exponent
bit-width (1..11), y = total stores at sites with that required width
(log scale). Bars are stacked per bench (turbo palette). Reference
vertical bands mark the FP8 E4M3 (≤4), FP8 E5M2 (≤5), bf16 / FP32 (≤8),
and FP64 (≤11) cut-offs. The picture answers "how much of each bench's
write traffic could live in a tiny-float exponent budget?"
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

THRESHOLDS = [
    (4,  "FP8 E4M3"),
    (5,  "FP8 E5M2"),
    (8,  "bf16 / FP32"),
    (11, "FP64"),
]


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    df = df.dropna(subset=["required_e_bits"])
    df["required_e_bits"] = df["required_e_bits"].astype(int)

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.5),
                             sharex=True, sharey=True)

    cmap = plt.get_cmap("turbo")
    bins = np.arange(1, 13)  # 1..12; bin edges are integer-aligned

    for ax, atype in zip(axes, ("32bits", "64bits")):
        sub = df[df.alloc_type == atype]
        if sub.empty:
            ax.text(0.5, 0.5, f"no rows for {atype}",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=10, color="#888")
            continue

        benches = sorted(sub["bench"].unique())
        # Build a (n_benches, n_bins-1) volume matrix.
        M = np.zeros((len(benches), len(bins) - 1), dtype=float)
        for i, bench in enumerate(benches):
            bsub = sub[sub.bench == bench]
            counts, _ = np.histogram(bsub["required_e_bits"],
                                     bins=bins,
                                     weights=bsub["total"])
            M[i, :] = counts

        # Stacked bars on log y-scale: convert each stack into a sequence of
        # bar pieces by accumulating from bottom.
        x = bins[:-1]
        bottom = np.zeros_like(x, dtype=float)
        for i, bench in enumerate(benches):
            color = cmap(i / max(1, len(benches) - 1))
            ax.bar(x, M[i, :], bottom=bottom, width=0.85,
                   color=color, edgecolor="white", linewidth=0.3,
                   label=bench, log=False)
            bottom = bottom + M[i, :]

        # Reference threshold lines.
        for k, (b, lbl) in enumerate(THRESHOLDS):
            ax.axvline(b + 0.5, color="#444", lw=0.6,
                       linestyle="--", alpha=0.55, zorder=1)
            ax.text(b + 0.5, 1.0, f"  ≤{b}: {lbl}",
                    rotation=90, fontsize=6.5, color="#444",
                    va="bottom", ha="left",
                    transform=ax.get_xaxis_transform())

        ax.set_yscale("log")
        ax.set_title(atype, fontsize=10)
        ax.set_xlabel("required exponent bits", fontsize=9)
        ax.set_xticks(x)
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(which="both", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    axes[0].set_ylabel("# stores at sites with that width (log)", fontsize=9)
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=7, title="bench",
                    title_fontsize=7, ncol=1)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
