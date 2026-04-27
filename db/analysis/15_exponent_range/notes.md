# Q15 — Exponent range feasibility

## What the figure shows

For each `(bench, alloc_type)` group, two views of the IEEE-754 unbiased
exponent distribution of stored values:

- **Left panel — exponent span.** A horizontal bar runs from `min_exp` to
  `max_exp` over the *normal-finite* values (zeros, denormals, and
  inf/NaN are excluded by the `FILTER` in `query.sql`). The dot is
  `mean_exp`. Background bands mark the FP8 dynamic ranges; dotted
  vertical lines mark FP16, bf16/FP32 and FP64 limits.
- **Right panel — in-range share.** Two-column heatmap of
  `frac_in_e4m3_range` (unbiased exp ∈ [-9, 8]) and
  `frac_in_e5m2_range` (unbiased exp ∈ [-16, 15]) over *all* stores
  (including zeros, denormals and inf/NaN — those count as out-of-range
  for the purpose of FP8 representability).

Q15 is the range counterpart to Q12. Q12 asks "does the mantissa fit?"
(precision); Q15 asks "does the magnitude fit?" (range). Both must be
true for an FP8 mapping to be lossless.

## How to read the rows

A row whose blue range bar lies entirely inside the green E4M3 band has
no values that overflow / underflow FP8 E4M3 — the heatmap then reads
high (close to 100 %). When the bar extends into FP16 / FP32 / FP64
territory, those tail values fall outside FP8 and the heatmap drops.

Rows annotated *"no normal-finite values"* have only zeros, denormals
or inf/NaN bit patterns; the FILTER aggregates return NULL. Their
heatmap cells are 0 % by construction (denormals and inf/NaN are not
counted as in-range), but the underlying byte patterns are still
representable as FP8 zero — the figure is a feasibility lower bound,
not an upper bound, in those rows.

## The dominant pattern: 32-bit "non-FP" cluster at exp ≈ -118

A large group of `32bits` rows pin near `min_exp = max_exp ≈ -118`:
`bwaves`, `cactus`, `exchange2`, `fotonik`, `gcc`, `imagick`, `namd`,
`parest`, `perlbench`, `roms`. Unbiased exponent -118 corresponds to
biased exponent 9 — the bit pattern of small positive integers in the
range ~512..1023 reinterpreted as IEEE-754. (E.g. the int 1000 is
0x000003E8; reinterpreted as float32 it has biased exp 0..9.) These
rows are integer / pointer / length traffic miscategorised as floats by
alignment-derived `alloc_type`, the same caveat noted in Q12.

The takeaway: a row with `min_exp = max_exp = -118` and 0 / 0 in the
heatmap is *not* evidence against FP8 — it is evidence that the row
isn't really FP at all.

## Genuinely FP rows: who actually fits in FP8?

Of the rows whose values look like real floats (wide, non-degenerate
exponent span), the FP8 fit splits cleanly:

- **Near-100 % E4M3 fit.** `lbm · 64bits` 99/99, `namd · 64bits`
  98/99 (the dominant double-precision computation kernels in those
  benches stay in a tight magnitude band — `lbm`'s LBM coefficients
  and `namd`'s force / coordinate buffers).
- **Mostly fits in E4M3.** `cactus · 64bits` 64/66, `povray · 64bits`
  52/53, `blender · 64bits` 46/47, `cam4 · 64bits` 46/66.
- **Needs E5M2 (range), not E4M3.** `parest · 64bits` 7/38,
  `roms · 64bits` 32/55, `wrf · 32bits` 38/54 — the extra range
  matters: roughly 20–30 percentage points of values live in
  exponents [-16, -10] ∪ [9, 15] that E4M3 cannot reach.
- **Out of FP8 range entirely.** `xz · 64bits` (mean_exp ≈ 200,
  max_exp 1023) and `wrf · 64bits` (mean_exp ≈ -65, min_exp -1022)
  span the full FP64 dynamic range — these are not FP8 candidates
  even before considering precision.

## E4M3 vs E5M2: the column delta is small

Across the table, E5M2 typically gains 0–4 percentage points over
E4M3 — the extra exponent bit only matters where the distribution has
a heavy tail. The notable exceptions are `parest · 64bits` (7 → 38),
`roms · 64bits` (32 → 55), `cam4 · 64bits` (46 → 66) and
`wrf · 32bits` (38 → 54). Combine with Q12: for these rows the
binding constraint is range, not precision; for the lbm / namd / cactus
group it is the other way around.

## Caveats

- The in-range fractions are *necessary, not sufficient* for FP8
  feasibility. A value can have an exponent in [-9, 8] yet still
  require more than 3 mantissa bits — Q12 is the matching precision
  filter.
- Denormals and zeros count as 0 in the in-range numerator but are
  representable as FP8 zero in practice. The heatmap therefore
  understates feasibility for benches dominated by zeros / denormals
  (e.g. `fotonik · 64bits` is 99 % zero — Q12 puts it at 99 % FP8
  feasible, while Q15 reads 0 / 0 because no value is *normal* AND
  in-range).
- `alloc_type` is alignment-derived, not type-tagged; the -118 cluster
  on 32-bit rows is the reinterpreted-integer artefact, not a property
  of float storage.
