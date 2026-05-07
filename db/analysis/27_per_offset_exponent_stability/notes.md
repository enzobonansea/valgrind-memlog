# 27_per_offset_exponent_stability — per-offset IEEE exponent stability

## What the experiment measures

Low-precision number formats (FP8, MXFP4, NF4, …) reduce dynamic range
by stripping exponent bits and replacing them with a *shared scale*. The
question of how often that scale must be recomputed is the
"granularity" choice:

| granularity | scale lifetime | precision | overhead |
|---|---|---|---|
| per-tensor | one scale for the whole buffer | low (one outlier dominates) | minimal |
| per-channel | one scale per offset (column) | exact if exponents are stable per offset | one scalar per column |
| per-token / per-block | recompute every K stores | best | per-block scale page |

This query measures, for each top allocation site and each offset that
received ≥ 2 stores, the unbiased IEEE-754 exponent range
(`max - min`). Two summary numbers per site:

- `frac_constant_exp` — share of offsets whose exponent never changed.
  Close to 1 ⇒ per-channel scaling is *exact*.
- `mean_exp_range`  — mean exponent spread per offset. Close to 0 ⇒
  per-channel scaling is exact; large ⇒ only per-token/per-block
  scaling recovers full precision.

`p95_exp_range` and `median_exp_range` are kept as the worst-5%-tail
and the paper-friendly summary respectively. Zero/denormal/NaN/Inf
values are excluded from the exponent computation — they don't
constrain the scale.

The query keeps the top-20 sites globally per bench (ranked by
`distinct_offsets`), with `HAVING SUM(distinct_offsets) >= 100` to drop
sites whose exponent spread would be statistically meaningless.
Per-bench iteration plus a small `addr_stack` lookup keep the per-offset
hash bounded — earlier shapes that carried the full `alloc_stack`
string into the per-offset state OOM'd on cam4 (~600 M unique
offsets).

## result.csv

121 rows. Columns: `bench`, `alloc_type`, `site`, `distinct_offsets`,
`frac_constant_exp`, `mean_exp_range`, `median_exp_range`,
`p95_exp_range`.

## figure.svg

Scatter — one point per (bench, site, alloc_type):

- x = `mean_exp_range` (log scale, clipped at 0.05 so constant-exponent
  sites still appear).
- y = `frac_constant_exp` (0–1).
- marker size ∝ log `distinct_offsets`.
- colour = bench (turbo palette).

Two soft regions are shaded: green at the top ("per-channel scaling
exact") for sites with ≥80 % constant-exponent offsets, orange at the
bottom ("per-token scaling required") for sites with ≤20 %.

## Headline observations

- **Per-channel scaling is exact for a substantial population of hot
  sites.** Multiple top-volume sites cluster in the green region with
  `frac_constant_exp ≥ 0.8` and `mean_exp_range < 1` — including
  `lbm·LBM_allocateGrid` (49.6 M offsets, 100 % constant),
  `xz·sha_process` (1.0), `cam4·__tp_core_MOD_fyppm` (0.92), and
  `wrf·__module_diffusion_em_MOD_calculate_n2` (0.99).
- **A handful of cam4 / pop2 / wrf sites need per-token scaling.**
  cam4 `__phys_buffer_MOD_pbuf_allocate` and
  `__radae_MOD_initialize_radbuffer` carry mean exponent ranges
  ~1000 — these buffers cover scientific quantities whose magnitudes
  span the full FP64 dynamic range. Per-channel scaling would lose
  most of the precision; per-token scaling (or a wide-exponent format
  like FP64 itself) is the only safe answer.
- **Per-channel scaling is the right default.** The bulk of the
  measured offsets fall on the left half of the plot
  (`mean_exp_range ≤ 8` — the MXFP8 spread budget). Pairs naturally
  with Q14/Q19 (MX block-spread viability): the per-block scale story
  Q14 tells holds because, *within a block*, the offsets sharing that
  scale also tend to be exponent-stable individually.
- **`frac_constant_exp = 1.0` rows are constants.** Sites like
  `lbm·LBM_allocateGrid`, `xz·sha_process`, `xz·lzma_alloc` and
  `gcc·pool_alloc` write the same exponent at every offset for the
  whole run — these compress to a *single* shared exponent (E0 +
  mantissa) without any per-channel overhead.
- Pairs with Q15 (per (bench, alloc_type) exponent range — coarse),
  Q24 (per-site required exponent bits — also coarse), and Q14/Q19
  (per-block spread). Q27 is the *finest* granularity: exponent
  variance per individual byte offset.
