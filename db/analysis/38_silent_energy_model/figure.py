#!/usr/bin/env python3
"""Profile-gated silent-store elimination: energy threshold sweep.

Post-processing of 35_per_buffer_silent/result.csv (no query of its
own). Mechanism model: verify-before-write is enabled only on buffers
whose profiled silent fraction is >= a gating threshold t. Every store
to a gated buffer pays one verify read; every silent store to a gated
buffer squashes one write. With k = write/read energy ratio, the net
energy change in read-units is  S(t)*k - C(t), where C(t) is stores to
gated buffers and S(t) the silent stores among them. We report it as a
fraction of the workload's total write energy (T*k):

    f(t, k) = (S(t)*k - C(t)) / (T*k)

Panel (a): suite-wide f(t) for k in {2, 5, 10}. Panel (b): per-benchmark
net saving at each benchmark's own best threshold (k = 5), i.e. the
gains available when the gate is tuned per application, which is the
setting the per-buffer profile enables. Buffers below the profiling
noise floor (pairs < 1000) are never gated.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
Q35  = HERE.parent / "35_per_buffer_silent" / "result.csv"
OUT  = HERE / "figure.svg"

MIN_PAIRS  = 1000
THRESHOLDS = np.round(np.arange(0.05, 1.00, 0.05), 2)
RATIOS     = [2, 5, 10]
COLORS     = {2: "#56B4E9", 5: "#0072B2", 10: "#009E73"}
K_BARS     = 5


def sweep(df: pd.DataFrame) -> pd.DataFrame:
    """f(t, k) rows for one store population."""
    total = df["stores"].sum()
    rows = []
    eligible = df[df["pairs"] >= MIN_PAIRS]
    for t in THRESHOLDS:
        gated = eligible[eligible["silent_frac"] >= t]
        C, S = gated["stores"].sum(), gated["silent"].sum()
        for k in RATIOS:
            rows.append({"t": t, "k": k,
                         "f": (S * k - C) / (total * k) if total else 0.0})
    return pd.DataFrame(rows)


def main() -> None:
    df = pd.read_csv(Q35)

    suite = sweep(df)

    best = []
    for bench, g in df.groupby("bench"):
        s = sweep(g)
        s5 = s[s.k == K_BARS]
        i = s5["f"].idxmax()
        best.append({"bench": bench,
                     "f": max(s5.loc[i, "f"], 0.0),
                     "t": s5.loc[i, "t"]})
    best = pd.DataFrame(best).sort_values("f", ascending=False)

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(9.0, 5.6), gridspec_kw={"width_ratios": [1, 1.15]})

    for k in RATIOS:
        s = suite[suite.k == k]
        ax1.plot(s["t"], s["f"] * 100, color=COLORS[k], lw=2,
                 marker="o", ms=3.5, label=f"write = {k}$\\times$ read")
    ax1.axhline(0, color="#999", lw=0.8)
    ax1.set_xlabel("gating threshold $t$ (profiled silent fraction)",
                   fontsize=11)
    ax1.set_ylabel("net write-energy saved (%)", fontsize=11)
    ax1.set_title("suite-wide, single threshold", fontsize=11)
    ax1.tick_params(labelsize=10)
    ax1.grid(linestyle=":", alpha=0.4)
    ax1.set_axisbelow(True)
    ax1.legend(frameon=False, fontsize=10, loc="lower center")
    for spine in ("top", "right"):
        ax1.spines[spine].set_visible(False)

    y = np.arange(len(best))
    ax2.barh(y, best["f"] * 100, height=0.65, color="#0072B2",
             edgecolor="white", linewidth=0.4)
    ax2.set_yticks(y)
    ax2.set_yticklabels(best["bench"], fontsize=10)
    ax2.invert_yaxis()
    ax2.set_xlabel(f"net write-energy saved (%), $k={K_BARS}$,"
                   " per-bench best $t$", fontsize=11)
    ax2.set_title("per benchmark, tuned threshold", fontsize=11)
    ax2.tick_params(axis="x", labelsize=10)
    ax2.grid(axis="x", linestyle=":", alpha=0.4)
    ax2.set_axisbelow(True)
    for spine in ("top", "right"):
        ax2.spines[spine].set_visible(False)
    for i, (_, r) in enumerate(best.iterrows()):
        if r["f"] > 0:
            ax2.text(r["f"] * 100 + 0.4, i, f"t={r['t']:.2f}",
                     va="center", fontsize=7.5, color="#555",
                     family="monospace")

    fig.tight_layout()
    fig.savefig(OUT, format="svg", bbox_inches="tight")
    s5 = suite[(suite.k == 5)]
    print("suite best (k=5):", s5.loc[s5.f.idxmax()].to_dict())
    print(best.head(8).to_string(index=False))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
