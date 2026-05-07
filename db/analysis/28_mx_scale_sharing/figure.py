#!/usr/bin/env python3
"""MX scale-sharing efficiency at block size 32.

For each (bench, alloc_type), `overall_scale_share = distinct_scales /
blocks` measures how compressible the per-block scale page is. Low values
(≪ 1) mean many blocks share the same shared exponent — the per-block
scale overhead is amortizable. Values near 1 mean every block needs its
own distinct scale and the scale page is incompressible.

Two panels (32bits / 64bits). Per panel, one horizontal log-x bar per
bench. The right margin annotates `mean_per_buffer_scale_share` (the
within-buffer scale variety) and the absolute block count, so the
"distinct_scales / blocks" ratio can be read in context.

Block size 32 is plotted; in this dataset the {16, 32, 64} sweep is
flat — all three sizes produce the same per-buffer scale-share
statistics (the snapshot rolls up to identical per-buffer state).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

ALLOC_TYPES = ["32bits", "64bits"]
COLORS = {"32bits": "#0072B2", "64bits": "#56B4E9"}
BLOCK_SIZE = 32


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
    df = df[df.block_size == BLOCK_SIZE]

    # Sanity-print: verify the {16,32,64} sweep is genuinely flat.
    full = pd.read_csv(HERE / "result.csv")
    flat = (full.groupby(["bench", "alloc_type"])["overall_scale_share"]
                .nunique() == 1).all()
    print(f"overall_scale_share constant across block_size: {flat}")

    benches = sorted(df["bench"].unique())

    fig, axes = plt.subplots(
        1, 2, figsize=(12.0, 6.5), sharey=True,
        gridspec_kw={"wspace": 0.55},
    )

    y = np.arange(len(benches))

    for ax, atype in zip(axes, ALLOC_TYPES):
        sub = (df[df.alloc_type == atype]
               .set_index("bench").reindex(benches))
        share = sub["overall_scale_share"].to_numpy(dtype=float)
        ax.barh(y, np.where(np.isnan(share), 0, share),
                height=0.65, color=COLORS[atype],
                edgecolor="white", linewidth=0.4, alpha=0.95)

        ax.set_yticks(y)
        ax.set_yticklabels(benches, fontsize=7)
        ax.invert_yaxis()
        ax.set_xscale("log")
        ax.set_xlim(1e-7, 2.0)
        ax.set_xlabel("distinct_scales / blocks  (log, lower = more sharing)",
                      fontsize=9)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_title(f"{atype}  (block size {BLOCK_SIZE})", fontsize=10)
        ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.axvline(1.0, color="#888", linestyle="--", linewidth=0.7,
                    alpha=0.6, zorder=0)

        # Right-margin annotation: per-buffer mean share + block count.
        for i, bench in enumerate(benches):
            mean_buf = sub.at[bench, "mean_per_buffer_scale_share"]
            n_blocks = sub.at[bench, "blocks"]
            if pd.isna(mean_buf):
                txt = "—"
            else:
                txt = f"buf {mean_buf:.3f} · {_fmt_count(n_blocks)} blk"
            ax.text(1.02, i, txt, ha="left", va="center",
                    fontsize=6.5, color="#444",
                    family="monospace",
                    transform=ax.get_yaxis_transform())

    fig.suptitle(
        "MX per-block scale page is highly compressible: "
        "median bench < 0.01 distinct scales per block",
        fontsize=10, y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
