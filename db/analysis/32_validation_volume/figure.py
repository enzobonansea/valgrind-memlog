#!/usr/bin/env python3
"""Validation §3 — testing volume per benchmark.

Two panels per bench, shared bench order:
  left  — total stores (log-x).
  right — distinct buffers vs distinct call sites, grouped bars on a
          shared log-x axis. The horizontal gap between the two bars is
          the per-site reuse factor (buffers/site): a tall gap means a
          few sites allocated many buffers (loops, constructors); equal
          bars mean every site allocated exactly once.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT  = HERE / "figure.svg"

C_STORES = "#0072B2"
C_BUF    = "#E69F00"
C_SITE   = "#CC79A7"


def main() -> None:
    df = pd.read_csv(HERE / "result.csv").sort_values("stores")
    n = len(df)
    y = np.arange(n)

    fig, (ax_s, ax_b) = plt.subplots(1, 2, figsize=(12.0, 7.0), sharey=True)

    ax_s.barh(y, df["stores"].clip(lower=1), color=C_STORES,
              edgecolor="white", linewidth=0.4)
    ax_s.set_yticks(y)
    ax_s.set_yticklabels(df["bench"], fontsize=8)
    ax_s.set_xscale("log")
    ax_s.set_xlabel("stores (log)")

    h = 0.38
    ax_b.barh(y - h/2, df["buffers"].clip(lower=1),    height=h,
              color=C_BUF,  edgecolor="white", linewidth=0.4,
              label="distinct buffers")
    ax_b.barh(y + h/2, df["call_sites"].clip(lower=1), height=h,
              color=C_SITE, edgecolor="white", linewidth=0.4,
              label="distinct call sites")
    ax_b.set_xscale("log")
    ax_b.set_xlabel("count (log)")
    ax_b.legend(loc="lower right", frameon=False, fontsize=8)

    # Annotate buffers/site ratio at the right edge of each row so the
    # log-bar gap is quantified — perlbench's 1565× isn't legible from bar
    # length alone on a shared axis.
    xmax = max(df["buffers"].max(), df["call_sites"].max())
    for yi, ratio in zip(y, df["buffers_per_site"]):
        txt = f"{ratio:.0f}×" if ratio >= 10 else f"{ratio:.1f}×"
        ax_b.text(xmax * 1.6, yi, txt, va="center", ha="left",
                  fontsize=7, color="#444")
    ax_b.set_xlim(right=xmax * 6)

    for ax in (ax_s, ax_b):
        ax.grid(axis="x", which="both", linestyle=":", alpha=0.4)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT, format="svg")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
