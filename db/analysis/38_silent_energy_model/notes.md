# 38_silent_energy_model — profile-gated silent-store elimination sweep

## What the experiment measures

No query of its own: post-processing of `35_per_buffer_silent/result.csv`.
First-order energy model of profile-gated verify-before-write. The gate
enables the check only on buffers whose profiled silent fraction is
`>= t` (and above the 1000-pair noise floor). Every store to a gated
buffer pays one verify read; every silent store there squashes one
write, priced at `k` reads (`k` = write/read energy ratio). Net saving
as a fraction of total write energy:

    f(t, k) = (S(t)·k − C(t)) / (T·k)

where `C(t)` = stores to gated buffers, `S(t)` = silent stores among
them, `T` = all stores.

## figure.svg

Left panel: suite-wide `f(t)` for `k ∈ {2, 5, 10}`. Right panel:
per-benchmark saving at each benchmark's own best threshold (`k = 5`),
annotated with the chosen `t`.

## Headline observations

- Single suite-wide threshold, `k = 5`: **15.3 % net write-energy saving
  at t = 0.2**. At `k = 10`: >20 %. At DRAM-like `k = 2` the mechanism
  still nets ~4 %, but only with a stricter gate (t ≈ 0.55) — the k=2
  curve goes negative at loose thresholds, which is the quantitative
  argument for profile-gating over always-on verify-before-write.
- Per-application tuning (what the per-buffer profile enables):
  `fotonik` 58 %, `lbm` 53 %, `pop2` 34 %, `bwaves` 27 %, `x264` 17 %,
  `wrf` 14 %; silence-immune apps (`namd`, `omnetpp`, `gcc`, …) gate
  nothing and lose nothing.
- The model is deliberately first-order: uniform per-op energies, no
  cache-hierarchy filtering. It ranks opportunities; it does not predict
  absolute savings.
