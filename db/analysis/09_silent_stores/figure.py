#!/usr/bin/env python3
"""Silent-store fraction per (bench, alloc_type).

Three side-by-side panels (32bits / 64bits / object). Per panel, one
horizontal bar per bench showing `silent_frac` — the fraction of stores
whose value matches the most recent prior write to the same
(alloc_addr, generation, offset). The right margin annotates the raw
counts (silent / stores_with_prev). Pairs with no prior-store traffic
are left blank.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

ALLOC_TYPES = ["32bits", "64bits", "object"]
# Wong-palette colour per panel.
COLORS = {"32bits": "#0072B2", "64bits": "#56B4E9", "object": "#009E73"}


def _fmt_count(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1e9:.1f}B"
    if n >= 1_000_000:
        return f"{n/1e6:.1f}M"
    if n >= 1_000:
        return f"{n/1e3:.1f}k"
    return str(int(n))


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")
    benches = sorted(df["bench"].unique())

    fig, axes = plt.subplots(
        1, 3, figsize=(12.0, 6.0), sharey=True,
        gridspec_kw={"wspace": 0.55},
    )

    y = np.arange(len(benches))

    for ax, atype in zip(axes, ALLOC_TYPES):
        sub = (df[df.alloc_type == atype]
               .set_index("bench")
               .reindex(benches))
        frac = sub["silent_frac"].to_numpy(dtype=float)

        ax.barh(y, frac, height=0.65, color=COLORS[atype],
                edgecolor="white", linewidth=0.4, alpha=0.95)

        ax.set_yticks(y)
        ax.set_yticklabels(benches, fontsize=7)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.0)
        ax.set_xlabel("silent-store fraction", fontsize=9)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_title(atype, fontsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        # Right-margin count annotation per row.
        for i, bench in enumerate(benches):
            n_prev = sub.at[bench, "stores_with_prev"]
            n_sil  = sub.at[bench, "silent"]
            if pd.isna(n_prev) or n_prev == 0:
                txt = "—"
            else:
                txt = f"{_fmt_count(n_sil)}/{_fmt_count(n_prev)}"
            ax.text(1.02, i, txt, ha="left", va="center",
                    fontsize=6.5, color="#444",
                    family="monospace",
                    transform=ax.get_yaxis_transform())

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
