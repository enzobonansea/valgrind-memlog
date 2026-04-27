# Q12 — Lossless reduced-precision feasibility

## What the figure shows

For each `(bench, alloc_type)` group we estimate the share of stored
values that, *if interpreted as IEEE-754 floats*, would round-trip
exactly through a target reduced-precision format. A value qualifies
when its mantissa has at least N trailing zero bits, where N is the
number of mantissa bits the target drops:

| target    | drops (32-bit value) | drops (64-bit value) |
|-----------|---------------------:|---------------------:|
| FP8 E4M3  | 20                   | 49                   |
| FP8 E5M2  | 21                   | 50                   |
| bfloat16  | 16                   | 45                   |
| FP16      | 13                   | 42                   |
| FP32      | n/a (already FP32)   | 29                   |

Cell color and label: percentage of stores in that row that meet the
threshold. For 32-bit rows the FP32 column is trivially 100%
(a 32-bit float *is* FP32).

## How to read the rows

Within a row, lower-precision targets are stricter (more mantissa bits
dropped → larger trailing-zero requirement). Reading left-to-right,
percentages should be non-decreasing across the FP8/bf16/FP16
sequence (modulo the 20-vs-21 swap between E4M3 and E5M2). The
column where a row first jumps to ~100% is the cheapest format that
losslessly captures that benchmark's stored values.

## The dominant pattern: bimodality

Most rows show **near-identical percentages across FP8, bfloat16, and
FP16** (e.g. `gcc · 32bits` 54/54/54/54, `bwaves · 32bits`
75/75/75/75, `gcc · 64bits` 71/71/71/71/71). This is not a bug — it
is the signal.

The trailing-zero distribution of stored words is strongly bimodal:

- **Mode A — random-looking bits.** A handful of trailing zeros
  (typically 0–5). Passes *none* of the format thresholds.
- **Mode B — structural zeros.** Mantissa is entirely (or almost
  entirely) zero — 23 trailing zeros on 32-bit values, 52 on 64-bit.
  Passes *every* threshold.

Because the non-FP32 thresholds (13, 16, 20, 21 for 32-bit values;
42, 45, 49, 50 for 64-bit) are all "high" relative to the mantissa
width, almost no value lies *between* the highest and lowest
threshold. A given row's value is essentially the share of words in
Mode B.

The columns that *do* differentiate are FP32 (for 64-bit rows, with a
much looser threshold of 29 trailing zeros) and, to a lesser extent,
FP16 versus FP8 on a few specific benches (`leela · 32bits`
56/55/61/64, `cam4`, `wrf`, `pop2 · 64bits` 63/63/66/68/80). These
are benches whose stores include some genuinely intermediate-precision
values, not just zeros and noise.

## Caveat: alloc_type is alignment-derived

`alloc_type` is bucketed from the access *alignment*, not from a
type tag. Most 32-bit-aligned stores in real workloads are integers,
pointers, flags, or lengths — not floats. The heuristic is applied
uniformly anyway, which inflates Mode B for integer-heavy workloads:
small integers and zeros, reinterpreted as IEEE-754, have
all-zero mantissas and trivially pass every threshold.

So a row reading "75% representable in FP8" should be read as "75%
of these byte patterns *would* round-trip to FP8 under a float
reinterpretation" — not "this benchmark could run in FP8." The
former is a useful upper bound on lossless format reduction; the
latter would require a type-aware filter (Q13 onward).

## Headline observations

- **Almost no benchmark needs full FP64 precision.** For 64-bit
  rows, the FP32 column is the only one that varies meaningfully
  from the rest, and even there the lift is modest in most rows
  (`namd` 0.6%→1%, `parest` 26%→29%, `pop2` 63%→80%). The
  remaining 50–70% of "double-precision" stores in many benches are
  Mode-B values that any narrower format would also capture exactly.
- **A few benches are genuinely format-sensitive.** `pop2 · 64bits`
  shows the cleanest staircase (63 / 63 / 66 / 68 / 80), suggesting
  a meaningful spread of mantissa precisions. `leela · 32bits` and
  `cam4 · 32bits` show similar (smaller) effects.
- **Outliers worth flagging.** `fotonik · 64bits` is 99% Mode B —
  almost all 64-bit stores are zero-mantissa. `imagick · 64bits` and
  `nab · 64bits` are 0% across the board (random-looking mantissas
  on every store, possibly because the totals are tiny — 1M and 7
  rows respectively). `namd · 64bits` is also flatly low (~0.6%
  Mode B), the only large 64-bit row whose stores look uniformly
  random under a float reinterpretation.
