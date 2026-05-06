# 14_mx_feasibility — MXFP8 block-viability per (bench, alloc_type)

## What the experiment measures

OCP Microscaling (MX) formats encode a block of N consecutive values as
a shared E8M0 scale (the maximum exponent in the block) plus per-element
low-precision mantissas. A block is *MX-viable* for a low-precision
mantissa format when the unbiased exponent spread across its elements is
at most `THRESHOLD`; if it exceeds the threshold the smallest values
underflow once the shared scale is stripped out.

This query uses the OCP defaults that match `analyze_fp8_mx.py`:
**block size 32**, **threshold 8** (MXFP8 E4M3: 4 exponent bits, ~8 bits
of headroom after one is consumed as bias). Q19
(`19_mx_block_sweep`) sweeps the block size for the same threshold.

The metric is computed on the **last-write snapshot** per
`(alloc_addr, generation, offset)` — the buffer's final state, not the
full trace — using `arg_max(value, rn)`. Zero, denormal, NaN and Inf
contribute no exponent and don't constrain the spread; a block with
fewer than 2 finite-normal values is automatically counted as viable.

## result.csv

One row per `(bench, alloc_type)` with `alloc_type` ∈ {`32bits`,
`64bits`}. Columns:

- `blocks` — number of 32-element blocks across all buffers in the
  snapshot.
- `viable_blocks` / `viable_frac` — count and fraction with fewer than
  two finite-normal exponents OR `max - min ≤ 8`.
- `mean_spread`, `median_spread`, `max_spread` — exponent spread stats
  computed over blocks with at least two finite-normal values
  (`FILTER (WHERE valid_n >= 2)`); empty when no such block exists.

44 rows.

## figure.svg

`viable_frac` is **1.0 for every (bench, alloc_type) pair**. With no
variance to plot on the colour axis, the figure documents the
**volume** of blocks per row on a log-scaled horizontal bar chart
(green bars), with each row annotated `100% viable · max spread = K`.
Bars span seven orders of magnitude — from `omnetpp · 32bits` at 7
blocks up to `wrf · 32bits` at ~866 M blocks — so log scaling is
essential. The title states the headline directly: "MX-FP8
(block=32, threshold=8): every block is viable".

## Headline observations

- **MXFP8 viability at block 32, threshold 8 is universal across these
  benches.** No bench produces a single block whose finite-normal
  exponents span more than 8 — the `max_spread` column is uniformly 0
  (or empty when no block had ≥2 finite-normal values).
- That 0 is a very strong statement: across ~1.9 G snapshot blocks,
  the worst block has `max_e − min_e = 0`. This is consistent with the
  Q06/Q12 picture — most "32-bit" and "64-bit" stores in this
  alignment-bucketed trace are integers, pointers, zeros, or scaled
  scientific values whose exponents cluster tightly.
- The block-size choice is therefore not load-bearing for this trace
  (Q19 confirms: viability is flat across {8, 16, 32, 64, 128}).
  Block 32 is the OCP standard, not an empirically-tuned optimum.
- Coupled with Q15 (exponent-range fit) and Q24 (per-site required
  exponent bits), MXFP8 looks like an unrestricted choice on the
  workloads represented here — at least under the alignment-bucketed
  reinterpretation. Type-aware filtering (e.g. via `13_per_function_*`)
  would tighten the claim.
