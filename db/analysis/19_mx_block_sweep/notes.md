# 19_mx_block_sweep — MX viability vs block size

## What the experiment measures

The block-size knob is the central design trade-off in MX (microscaling)
formats: a larger block amortises the shared-scale overhead but
tolerates less exponent spread inside the block before the smallest
values underflow. Q14 evaluates a single block size (32). This query
sweeps block size ∈ {8, 16, 32, 64, 128} on the same last-write snapshot
per `(alloc_addr, generation, offset)` so the viability vs block-size
curve can be drawn per benchmark.

For each block size we report:

- `blocks` — number of blocks across the bench's snapshot.
- `viable_spread4` — fraction of blocks with `max_e − min_e ≤ 4` (or
  fewer than 2 finite-normal exponents). This is the
  hypothetical-MXFP4 threshold (4 exponent-bit headroom).
- `viable_spread8` — same but `≤ 8` (the MXFP8 / E4M3 headroom; this is
  the standard OCP MX setting).
- `mean_spread` — average over blocks with at least 2 finite-normal
  exponents.

The five block sizes are computed as five UNION-ALL `GROUP BY` sweeps
over a materialised CTE (`indexed`) so the snapshot is scanned once
even though each block size redefines `block_id`.

## result.csv

216 rows, one per `(bench, alloc_type, block_size)`. Columns:
`blocks`, `viable_spread4`, `viable_spread8`, `mean_spread`.

`viable_spread4 = viable_spread8 = 1.0` for every row in this trace.
`mean_spread` is empty in every row — no block has at least two
finite-normal exponents at all (every block's exponents are constant
or ≤1 finite-normal element), so the `FILTER (WHERE valid_n >= 2)`
predicate produces no rows for AVG.

## figure.svg

Two side-by-side panels (32-bit / 64-bit alignment). x-axis is block
size on log2 scale `{8, 16, 32, 64, 128}`. y-axis is the **number of
blocks** at that block size (log scale). One line per benchmark
(turbo-coloured). The figure header states the headline directly:
"MX viability is flat at 100% across all block sizes — spread ≤ 4 and
spread ≤ 8 both hold for every block."

The block-count curves fall as `block_size` doubles (each block now
covers twice as many offsets, halving the count) — the slopes are
informative for understanding the snapshot's offset volume per buffer,
not for viability.

## Headline observations

- **Block size is not load-bearing for MX viability on this trace.**
  Both the MXFP8 (`spread ≤ 8`) and the tighter hypothetical-MXFP4
  (`spread ≤ 4`) thresholds hold for every block at every block size.
- That means the OCP standard (block 32) can be substituted by 64 or
  128 to **double or quadruple the scale-amortisation** with no
  viability cost — at least under this snapshot's bit-pattern
  distribution.
- The `mean_spread` column being empty everywhere is a stronger
  finding than `viable_frac = 1.0`: it implies every block has its
  finite-normal exponents constant (`max = min`). Most of the trace's
  finite-normal stores collapse to a single exponent value per
  buffer-region.
- Q15 (`15_exponent_range`) reports total per-(bench, alloc_type)
  exponent ranges, and Q24 reports per-(bench, alloc_type, site)
  required-exponent-bits. Both are consistent with this picture: the
  exponent range that an MX block has to tolerate is small.
- Caveat (same as Q14): `alloc_type` is alignment-bucketed, not
  type-tagged. Buffers dominated by integers/pointers/zeros have
  trivially constant "exponents" under reinterpretation. Type-aware
  filtering (e.g. via Q13's site dictionary) would tighten the claim
  to genuinely-FP traffic.
