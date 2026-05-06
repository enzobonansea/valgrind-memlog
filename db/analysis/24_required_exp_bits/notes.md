# 24_required_exp_bits — minimum exponent bit-width per allocation site

## What the experiment measures

A custom IEEE-754-like format reduces precision by trimming both
mantissa bits *and* exponent bits. This query answers the second
question: **how many exponent bits does each allocation site actually
need** to span its observed dynamic range without overflowing a
narrow exponent field.

For each store we extract the unbiased IEEE-754 exponent (after
excluding zero, denormal, NaN and Inf — these don't constrain the
range). Per allocation site (the first non-allocator stack frame,
same skip-list as Q13/Q16) we record `min_e`, `max_e`, the resulting
`exp_range = max_e − min_e + 1`, and the minimum bit-width
`required_e_bits = ⌈log₂(max(exp_range, 2))⌉`.

Reference exponent widths:

| width | format               |
|------:|----------------------|
| 4     | FP8 E4M3             |
| 5     | FP8 E5M2             |
| 8     | bfloat16 / FP32      |
| 11    | FP64                 |

A site with `required_e_bits ≤ 4` is a candidate for FP8 E4M3 from a
*range* perspective; combine with Q12/Q13 (precision via mantissa
trailing zeros) to identify functions that fit on both axes.

The query keeps the top-20 sites globally per bench (ranked by
`total`), with `HAVING SUM(total) >= 1000` to drop sites whose range
estimate would be statistically meaningless.

## result.csv

144 valid rows (a few sites contain literal commas in C++ template
parameter lists; pandas's CSV parser handles them correctly via
quoting). Columns: `min_e`, `max_e`, `exp_range`, `required_e_bits`,
`total`.

## figure.svg

Two side-by-side panels (32-bit / 64-bit alignment). x = required
exponent width (1..11). y = total stores at sites needing that width
(log scale). Bars are stacked per benchmark (turbo palette). Dashed
vertical reference lines mark `≤4: FP8 E4M3`, `≤5: FP8 E5M2`,
`≤8: bf16/FP32`, `≤11: FP64`.

A bench whose mass piles up at low x can drop into a tiny-float
exponent budget; mass at x=11 is locked into FP64 by range alone.

## Headline observations

(Across the top-20 sites per bench, ~8.8 G stores total.)

- **The full FP8 E4M3 exponent (≤4 bits) covers only 6.7% of total
  store volume**, but the 64-bit-aligned subset alone is 9.8% — a
  sizeable absolute count (559 M stores) of *individual functions*
  whose exponent ranges already fit FP8.
- **At 32-bit alignment, no bench needs more than 8 exponent bits**
  (since FP32 has 8 itself). 100% of 32-bit traffic in the top-20
  sites is bf16/FP32-range-compatible.
- **At 64-bit alignment, 72.3% of stores fit ≤8 exponent bits.** This
  is the bf16/FP32 cutoff: nearly three-quarters of `64bits` traffic
  in these top sites could move to bf16 *if* mantissa precision also
  permits.
- **27.7% of 64-bit traffic genuinely needs more than 8 exponent
  bits.** These are the functions whose range exceeds bf16 — e.g.
  `cam4 · __dyn_comp_MOD_dyn_run` (10 bits, range -502..19),
  `cam4 · __phys_buffer_MOD_pbuf_allocate` (11 bits, range
  -502..1023), `bwaves · shell_` (9 bits, range -437..11). Many of
  these wide-range sites are not actually using all the magnitudes
  they have headroom for — a denormal-friendly tiny float with
  saturating arithmetic could absorb them.
- **`required_e_bits = 1` rows represent constants.** A site whose
  every store carries the same exponent (e.g. `bwaves · 32bits ·
  MAIN__` with `min_e = max_e = -118`) compresses to a single
  shared exponent — pure E0 + mantissa storage suffices.
- This figure is the *range* counterpart to Q15
  (`exponent_range` per (bench, alloc_type) only) and the
  per-function counterpart to Q12. Combine with Q13's precision
  feasibility for the both-axes view.
