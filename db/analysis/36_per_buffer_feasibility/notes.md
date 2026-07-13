# 36_per_buffer_feasibility — lossless representability per (bench, buffer)

## What the experiment measures

Same trailing-zero criterion as `12_format_feasibility` — a stored value
is losslessly representable in a reduced format when its IEEE-754
mantissa carries at least N trailing zeros (32-bit: E4M3 ≥ 20, E5M2 ≥ 21,
bf16 ≥ 16, FP16 ≥ 13; 64-bit: E4M3 ≥ 49, E5M2 ≥ 50, bf16 ≥ 45,
FP16 ≥ 42, FP32 ≥ 29) — but the fraction is kept per individual buffer
`(alloc_addr, generation)` instead of aggregating to `(bench, alloc_type)`.
`object`-typed allocations are excluded, as in Q12.

## result.csv

One row per buffer (347,802 rows): `bench, addr, generation, alloc_type,
alloc_size, total` and `pct_fp8_e4m3 / pct_fp8_e5m2 / pct_bf16 /
pct_fp16 / pct_fp32` (fraction of the buffer's stores meeting each
threshold; `pct_fp32` is 1.0 by construction for 32-bit buffers).

## figure.svg

Three panels (FP8 E4M3 / bfloat16 / FP32), same visual language as Q35:
one row per benchmark (sorted by store-weighted bf16 aggregate), one dot
per buffer, dot area ∝ log10(stores), colour = alloc_type, black tick =
the benchmark's store-weighted aggregate (Q12's number). FP32 panel
plots 64-bit buffers only. Top 400 buffers ≥ 1000 stores per bench;
right margin reports plotted/total and store coverage (70 % of the
suite's stores).

## Headline observations

- **Representability is all-or-nothing at buffer level.** Dots pile at
  0 and 1: suite-wide, 45 % of stores live in buffers below 5 %
  bf16-representability and 7.7 % in buffers above 95 %; the middle is
  thin.
- **The benchmark aggregate misdescribes the split**, mirroring the
  silent-store census: only 24 % of the suite's stores live in buffers
  whose bf16 representability is within ±5 points of their benchmark's
  aggregate (FP32: 35 %). `wrf` reads 33 % aggregate bf16 but only 6 %
  of its stores sit in buffers near that value.
- Caveat unchanged from Q12: alloc_type is alignment-derived, so
  integer/pointer traffic inflates representability; read as an upper
  bound.
