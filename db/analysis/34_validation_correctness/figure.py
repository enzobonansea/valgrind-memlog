#!/usr/bin/env python3
"""Validation §3 — IEEE-754 exponent-field class shares per (bench, alloc_type).

Per row we plot the four exponent-field bit-pattern shares as a stacked
horizontal bar:

  zero            value == 0 (scrubbed / zero-init memory)
  normal          1 <= exp_field <= max-1 (IEEE normal class)
  subnormal       exp_field == 0 and value != 0 (IEEE subnormal class
                  bit pattern; also matches small-magnitude integers)
  inf_nan         exp_field saturated (IEEE inf/NaN class bit pattern)

These are *bit-pattern* shares — the figure makes no claim that any
individual value is a float. A capture bug would manifest as a bench
whose 64-bit row deviates sharply from the IEEE-realistic pattern
(massive inf/nan share, random-looking distributions, etc.). Two panels
mirror the binary64 / binary32 interpretations. The `object` rows are
omitted: they carry no exponent field by definition.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

# Wong-palette: zero=neutral grey, normal=blue (the dominant healthy class),
# subnormal=orange (the marker class for small-magnitude integers), inf/nan
# = vermilion (would jump out if a capture bug planted them).
COLORS = {
    "zero":      "#999999",
    "normal":    "#0072B2",
    "subnormal": "#E69F00",
    "inf_nan":   "#D55E00",
    "other":     "#DDDDDD",
}


def _fmt_count(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1e9:.1f}B"
    if n >= 1_000_000:
        return f"{n/1e6:.1f}M"
    if n >= 1_000:
        return f"{n/1e3:.1f}k"
    return str(int(n))


def _panel(ax, df, atype, suffix):
    sub = (df[df.alloc_type == atype]
           .set_index("bench")
           .sort_index(ascending=True))
    benches = list(sub.index)
    y = np.arange(len(benches))

    cats = [
        ("zero",      sub["frac_zero"]),
        ("normal",    sub[f"frac_normal_{suffix}"]),
        ("subnormal", sub[f"frac_subnormal_{suffix}"]),
        ("inf_nan",   sub[f"frac_inf_nan_{suffix}"]),
    ]
    fracs = {name: s.fillna(0).to_numpy(dtype=float) for name, s in cats}
    total = sum(fracs.values())
    fracs["other"] = np.clip(1.0 - total, 0, 1)

    left = np.zeros(len(benches))
    for name in ("zero", "normal", "subnormal", "inf_nan", "other"):
        ax.barh(y, fracs[name], left=left, height=0.7,
                color=COLORS[name], edgecolor="white", linewidth=0.4,
                label=name.replace("_", "/"))
        left += fracs[name]

    ax.set_yticks(y)
    ax.set_yticklabels(benches, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("share of stores", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    ax.set_title(f"{atype} (binary{suffix[1:]} interpretation)", fontsize=10)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    for i, bench in enumerate(benches):
        n = sub.at[bench, "stores"]
        ax.text(1.02, i, _fmt_count(int(n)), ha="left", va="center",
                fontsize=6.5, color="#444",
                family="monospace",
                transform=ax.get_yaxis_transform())


def main() -> None:
    df = pd.read_csv(HERE / "result.csv")

    fig, axes = plt.subplots(
        1, 2, figsize=(12.0, 7.5),
        gridspec_kw={"wspace": 0.55},
    )
    _panel(axes[0], df, "32bits", "f32")
    _panel(axes[1], df, "64bits", "f64")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5,
               frameon=False, fontsize=8, bbox_to_anchor=(0.5, -0.02))

    fig.suptitle(
        "IEEE-754 exponent-field class shares — bit-pattern audit "
        "(no claim that values are FP)",
        fontsize=10, y=0.995,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
