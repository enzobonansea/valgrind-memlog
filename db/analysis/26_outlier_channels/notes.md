# 26_outlier_channels — outlier-channel concentration per allocation site

## What the experiment measures

LLM-quantization papers (SmoothQuant, AWQ, LLM.int8(), QuIP#) all hinge
on the same empirical fact: in floating-point activations and weights,
quantization error is dominated by a *small fixed set* of outlier
"channels" — offsets that consistently hold large-magnitude values.
If the outliers concentrate at a few stable offsets, a per-channel
scale (one scalar per offset) recovers the precision lost to
truncation. If they spread everywhere, only per-tensor scaling — or a
mixed-precision split that keeps the outlier rows in a wider format —
is safe.

The offset axis in Memlog *is* the channel axis at runtime, so we can
test directly whether SPEC workloads exhibit the same per-channel
concentration that LLM quantization papers report on transformer
activations.

For each (bench, alloc_site, alloc_type):

- `total` — number of non-zero stores by this site.
- `n_outlier_999` — stores whose IEEE-754 magnitude (sign bit masked
  off) exceeds the per-stack 99.9th-percentile threshold.
- `distinct_offsets` — distinct offsets touched by the site (HLL).
- `outlier_offsets` — distinct offsets that ever carry a 99.9% outlier
  (HLL).
- `channel_frac = outlier_offsets / distinct_offsets` — the headline
  metric. Close to 0 ⇒ outliers concentrate at a stable handful of
  channels (per-channel scaling exact). Close to 1 ⇒ outliers spread
  uniformly (per-tensor / mixed-precision required).

The query keeps the top-20 sites per bench (ranked by total store
volume), with `HAVING SUM(total) >= 1000` to drop trivial sites.

`distinct_offsets` and `outlier_offsets` are HLL estimates rather than
exact counts — an exact per-(stack, offset) pre-aggregate spills
> 200 GB on cam4-class benches because some Fortran array sites touch
millions of distinct offsets in one allocation, blowing (stack ×
offset) cardinality into the billions. HLL state is bounded per stack
regardless of offset count, so the query stays at zero spill.

## result.csv

179 rows across 23 benches (deepsjeng has no qualifying sites). Columns:
`bench`, `alloc_type`, `site`, `total`, `n_outlier_999`,
`distinct_offsets`, `outlier_offsets`, `channel_frac`.

## figure.svg

Scatter — one point per (bench, site, alloc_type):

- x = `distinct_offsets` (log scale, buffer-size proxy).
- y = `channel_frac` (0–1).
- marker size ∝ log `total`.
- colour = bench (turbo palette).

Two soft regions are shaded: green at the bottom
("per-channel scaling viable") for sites with `channel_frac ≤ 0.05`,
orange at the top ("per-tensor / mixed-precision required") for sites
with `channel_frac ≥ 0.5`.

## Headline observations

- **Per-channel scaling is viable for the bulk of hot sites.** The
  green band absorbs the majority of high-volume points: bwaves
  `shell_` (73 M offsets, channel_frac = 0.019), cam4
  `__dyn_comp_MOD_dyn_run` (22 M offsets, 0.0017), lbm
  `LBM_allocateGrid` (57 M offsets, 0.002), xz `sha_process`
  (22 M offsets, 0.001), xz `lzma_alloc` (35 M offsets, 0.002), wrf
  `__module_alloc_space_0_MOD_alloc_space_field_core_0` (7.2 M
  offsets, 0.012). The same per-channel concentration pattern that
  quantization papers report on transformer activations holds on
  scientific Fortran arrays — outliers cluster at a tiny minority of
  positions.
- **A handful of sites need per-tensor / mixed-precision.**
  `imagick·AcquireAlignedMemory` (channel_frac = 0.82), `namd·
  Patch::readfile` (1.00), `pop2·__hmix_gm_MOD_init_gm` (0.99),
  `parest·SparsityPattern::reinit` 32-bit (1.00), `blender·
  zbuffer_solid` (0.99) and `cam4·__physics_types_MOD_physics_type_alloc`
  (0.995) all sit in the orange band — outliers occupy *every*
  channel. These are typically small dense buffers or tightly-packed
  index tables where the value distribution doesn't have heavy tails;
  the 99.9% threshold ends up close to the median and most channels
  qualify as "outlier".
- **`channel_frac = 0.0` rows are degenerate, not bugs.** cam4's
  initialiser sites (`__phys_buffer_MOD_pbuf_allocate`,
  `__dyn_comp_MOD_dyn_init`, `__radae_MOD_initialize_radbuffer`,
  `__cam_diagnostics_MOD_diag_allocate`) and mcf's
  `primal_net_simplex` / `resize_prob` show 0 outliers because the
  buffer's value distribution is so narrow that p999 = max — no value
  exceeds the threshold. These compress to a single shared scale (or a
  constant) without any per-channel infrastructure.
- **Buffer size predicts viability.** Sites with > 1 M distinct offsets
  almost always have `channel_frac < 0.05` (left-bottom of the plot);
  sites with < 10 K distinct offsets dominate the upper band. Big
  arrays have room for outliers to concentrate; small dense tables
  don't.
- Pairs with Q27 (per-offset exponent stability — *which* offsets are
  the stable channels) and Q24 (per-site required exponent bits — how
  much dynamic range each scale must cover). Q26 says outliers
  concentrate; Q27 says the scale at each channel rarely shifts; Q24
  says how wide each scale needs to be — together they make the
  per-channel-scaling case end-to-end.
