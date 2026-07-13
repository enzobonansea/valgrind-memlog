# 37_per_buffer_exp_range — IEEE-754 exponent range per (bench, buffer)

## What the experiment measures

The range half of per-buffer format convertibility, companion to
`36_per_buffer_feasibility` (the precision half). Per buffer
`(alloc_addr, generation)`: the observed unbiased-exponent window
`[min_e, max_e]` over its non-zero normal stores, plus `n_zero` (zeros,
representable in every format) and `n_special` (denormal / Inf / NaN).
A buffer converts to a standard format only if the window fits the
format's normal range: FP8 E4M3 `[-6, 8]`, E5M2 `[-14, 15]`,
bfloat16 / FP32 `[-126, 127]`. Same extraction as Q24, kept per buffer.

## result.csv

One row per FP-typed buffer (347,802 rows, matching Q36's population):
`bench, addr, generation, alloc_type, alloc_size, total, n_zero,
n_special, min_e, max_e`. `min_e`/`max_e` empty for buffers whose every
store is zero.

## Headline observations (from the join with Q36)

- The two-axis verdict confirms **12,724 buffers (0.60 B stores, 4.4 %
  of the suite) as fully bfloat16-convertible** and 2,587 64-bit buffers
  (0.32 B stores) as losslessly FP64→FP32 demotable.
- The range check **rejects candidates the mantissa view alone would
  approve**: 2,117 mantissa-passing buffers (0.09 B stores) exceed FP8
  E4M3's range; `fotonik`'s 64 MB grid fails bfloat16 outright (nonzero
  exponents span `[-189, -63]`).
- **12,083 confirmed buffers (0.57 B stores, 4.2 % of FP-typed traffic)
  only ever store zero** — trivially convertible, but better served by
  zero-aware compression than by format conversion. The numerically
  nontrivial confirmed population is 663 buffers / 0.10 B stores for
  FP32, led by `pop2` arrays holding a single exponent all run.
