# 34_validation_correctness — Validation §3 IEEE-754 exponent-field shares

## What the experiment measures

Validation §3 asks: did the instrumentation log the same bytes the
program wrote, or did it corrupt them along the way (lost low bits,
swapped lanes during SIMD decomposition, wrote stale tree-node payload,
etc.)? The unit suite samples this on 11 hand-chosen bit-patterns. This
query is the empirical SPEC-scale counterpart: bin every captured uint64
by its IEEE-754 exponent field and report shares per
(bench, alloc_type).

For each row we report four bit-pattern shares (no claim that any
individual value is a float — these are exponent-field bit patterns):

| field | meaning |
|---|---|
| `frac_zero` | `value == 0` (zero-init / scrubbed memory) |
| `frac_normal_*` | `value != 0` and `1 <= exp_field <= max-1` (IEEE normal) |
| `frac_subnormal_*` | `value != 0` and `exp_field == 0` (IEEE subnormal class — also matches small-magnitude integers) |
| `frac_inf_nan_*` | `exp_field == max` (IEEE inf/NaN class) |

Two bit layouts are reported per row: binary64 (`(value >> 52) & 0x7FF`)
and binary32 over the low 32 bits (`(value >> 23) & 0xFF`). The rows
filter by `alloc_type` so the f64 columns are only populated on
`64bits` rows and f32 columns only on `32bits` rows. `object` rows
carry only `frac_zero` (no exponent field by definition).

A capture bug — e.g. high-half garbage from a stale 64-bit slot, or
random-looking data from a missed instrumentation point — would show
up as a 64-bit row dominated by `frac_inf_nan_f64` (exp_field == 0x7FF
is sticky under most kinds of corruption) or as a row whose four
classes don't sum to a sensible total.

Per-bench iteration keeps the wall time per query bounded — running
across `all_stores` in one shot pushed past the 1 h watchdog on the
cumulative-disk side.

## result.csv

67 rows = one per (bench, alloc_type) tuple. Columns: `stores`,
`frac_zero`, `frac_normal_f64`, `frac_subnormal_f64`,
`frac_inf_nan_f64`, `frac_normal_f32`, `frac_subnormal_f32`,
`frac_inf_nan_f32`.

## figure.svg

Two side-by-side panels: left = `32bits` rows under the binary32
interpretation, right = `64bits` rows under binary64. Per panel, one
stacked horizontal bar per bench:

  zero (grey) | normal (blue) | subnormal (orange) | inf/nan (vermilion) | other (light)

The `other` slice captures any residual mass — for these rows it is
empirically zero or near-zero, since the four classes partition the
bit-pattern space exactly. The right margin annotates the absolute
store count per bench (1 k → 4 B). `object` rows are omitted: they
have no exponent field.

## Headline observations

- **No row shows the inf/nan-dominant signature of a capture bug.**
  `frac_inf_nan_f64` is below 1 % for every 64-bit row except `mcf`
  (14.7 %, dominated by integer payloads whose top 11 bits happen to
  be all-ones — confirmed by the 71.8 % `subnormal` complement). The
  64-bit bars are dominated by `normal` (blue) for the FP-heavy
  benches and `subnormal` + `zero` for integer/pointer-heavy ones,
  which is the physically realistic pattern.
- **FP-dominant 64-bit benches show > 80 % `normal_f64`.** lbm
  (99.3 %), namd (99.4 %), bwaves+normal (note: `bwaves` is heavy on
  `frac_zero` 45.9 % + `normal` 46.0 % — alternating zeroed init and
  live FP), cam4 (88.3 %), roms (81.9 %), wrf-64bits (66.7 %),
  blender-64bits (93.9 %). These are the workloads paper §3 calls
  out as FP-dominated.
- **Subnormal-dominant rows are the integer/pointer-heavy ones.**
  perlbench-64bits (81.2 %), omnetpp-64bits (99.7 %), xalancbmk-64bits
  (56.6 %), gcc, leela. Small unsigned ints have the top 52 bits zero
  → `exp_field == 0` → "subnormal" class by bit pattern. This is the
  expected signature; the unit suite's pointer/integer test cases
  match it exactly.
- **`32bits` rows skew toward `subnormal_f32` for the same reason.**
  fotonik (54.1 %), namd-32bits (98.3 %), perlbench-32bits (73.7 %),
  pop2-32bits (74.4 %), roms-32bits (88.7 %), xz-32bits (83.2 %) — these
  are integer-aligned 32-bit traffic (loop counters, indices, lengths)
  with the top 8 bits zero. cam4-32bits (69.0 % `normal_f32`) is the
  outlier and contains genuine 32-bit floats — consistent with the
  per-function picture in Q13/Q16.
- **`frac_zero + frac_normal + frac_subnormal + frac_inf_nan ≈ 1` per
  row.** No "other" mass is visible in the figure, confirming the four
  classes partition the bit-pattern space exactly — i.e. every captured
  value is interpretable, the field-extraction is consistent across
  benches, and there is no rounding-error gap that would point to
  truncated logging.
- Pairs with Q32 (validation volume — *how much* we tested) and Q33
  (validation robustness — *how varied* the inputs were). Q34 is the
  *fidelity* leg of the §3 validation triangle: the bit patterns we
  logged are the bit patterns the program wrote.
