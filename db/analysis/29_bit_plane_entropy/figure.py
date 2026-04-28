#!/usr/bin/env python3
"""Per-bit Shannon entropy of stored values, per (bench, alloc_type).

One line per (bench, alloc_type), x = bit position 0–63, y = entropy in
[0, 1]. Low-entropy positions compress well (predictable bits); high-
entropy positions are near random.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.5),
                             sharey=True, sharex=True)

    for ax, atype in zip(axes, ("64bits", "32bits")):
        sub = df[df.alloc_type == atype]
        benches = sorted(sub["bench"].unique())
        cmap = plt.get_cmap("turbo")
        for i, bench in enumerate(benches):
            row = sub[sub.bench == bench].sort_values("bit_pos")
            ax.plot(row["bit_pos"], row["entropy"],
                    color=cmap(i / max(1, len(benches) - 1)),
                    linewidth=0.9, alpha=0.85, label=bench)
        ax.set_title(atype, fontsize=10)
        ax.set_xlabel("bit position")
        ax.set_ylim(0, 1.05)
        ax.set_xlim(0, 63)
        ax.grid(linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    axes[0].set_ylabel("Shannon entropy")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                    frameon=False, fontsize=7, title="bench")
    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
