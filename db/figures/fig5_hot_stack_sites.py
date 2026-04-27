#!/usr/bin/env python3
"""Figure 5 — top 15 stack sites by store volume.

Horizontal log-x bar chart. Each row is one alloc-site stack trace; we
extract a short label (the topmost non-malloc frame) for the y-axis.
Bars are colored by bench. Argues for per-site optimization.
"""
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE    = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
OUT     = HERE / "fig5_hot_stack_sites.svg"

# Regex matches lines like "==NNN== by 0x... function_name (...)".
FRAME_RE = re.compile(r"by 0x[0-9A-Fa-f]+:\s+([^\s(]+)")


def short_label(site: str) -> str:
    """First non-malloc frame's function name, or '<unknown>'."""
    matches = FRAME_RE.findall(site)
    for m in matches:
        if m not in ("malloc", "calloc", "realloc"):
            return m[:48]
    return matches[0][:48] if matches else "<unknown>"


def main() -> None:
    df = pd.read_csv(RESULTS / "04_hot_stack_sites.csv")
    df["label"] = df["site"].apply(short_label)
    df = df.sort_values("stores")

    benches  = sorted(df["bench"].unique())
    cmap     = plt.get_cmap("tab20")
    color_of = {b: cmap(i / max(1, len(benches) - 1)) for i, b in enumerate(benches)}

    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    y       = range(len(df))
    bars    = ax.barh(y, df["stores"],
                       color=[color_of[b] for b in df["bench"]],
                       edgecolor="white", linewidth=0.4)

    yticklabels = [f"{b}: {l}" for b, l in zip(df["bench"], df["label"])]
    ax.set_yticks(list(y))
    ax.set_yticklabels(yticklabels, fontsize=8, family="monospace")
    ax.set_xscale("log")
    ax.set_xlabel("stores (log)")
    ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
