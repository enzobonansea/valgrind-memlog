# 28_mx_scale_sharing — distinct-shared-scale ratio across MX blocks

## What the experiment measures

OCP MX formats emit one E8M0 scale per block of N consecutive values
(see Q14, Q19). Q14 establishes that the *spread* within each block
fits — so the encoding is lossless. This query asks the next question:
how many of those per-block scales are *distinct*?

If the scale page across all blocks contains only a handful of distinct
values (say, 10 distinct scales for 10 M blocks), the per-block scale
overhead amortizes to almost nothing — the scale page compresses
trivially via run-length, dictionary, or row-level sharing. If every
block needs its own scale, the per-block overhead is unavoidable.

For each (bench, alloc_type, block_size) we report:

- `blocks` — total blocks across all snapshot buffers.
- `distinct_scales_total` — total distinct scale values, summed across
  buffers (treats each buffer's scale set as private).
- `overall_scale_share = distinct_scales_total / blocks` — global
  compressibility of the scale page (lower = more reuse).
- `mean_per_buffer_scale_share` — the within-buffer ratio averaged
  across buffers (low = blocks within a buffer agree on a scale).
- `median_per_buffer_scale_share` — the same, median.

Block sizes {16, 32, 64} are swept. Snapshot extraction uses
`arg_max(value, rn)` to take the last write per `(alloc_addr,
generation, offset)`. Zero / denormal / NaN / Inf contribute no scale.

## result.csv

99 rows = 33 (bench, alloc_type) pairs × 3 block sizes. Columns:
`blocks`, `distinct_scales_total`, `overall_scale_share`,
`mean_per_buffer_scale_share`, `median_per_buffer_scale_share`.

**Block-size sweep is flat in this dataset.** The {16, 32, 64} rows
within a (bench, alloc_type) pair are identical to many decimal places.
Each buffer's per-block scales already agree across granularities — the
within-buffer state is dominated by either (a) full constancy
(`COUNT(DISTINCT) = 1` regardless of how the buffer is partitioned)
or (b) wide variety, where every block has its own scale and finer
granularity adds blocks but not distinct scales proportionally. The
figure plots block size 32 as the OCP standard.

## figure.svg

Two side-by-side panels (32bits / 64bits). Per panel, one horizontal
log-x bar per bench with `overall_scale_share` (distinct scales /
blocks). The right margin annotates `mean_per_buffer_scale_share` and
the absolute block count. Reference dashed line at `share = 1.0`
(every block needs its own scale — incompressible page).

## Headline observations

- **The MX per-block scale page is highly compressible across the
  board.** For 64-bit traffic, almost every bench sits between 1e-7
  and 1e-2 — i.e. one distinct scale per 100 to 10 M blocks.
  `lbm·64bits` is the extreme: 50.9 M blocks, 6 distinct scales
  (1.2e-7). `bwaves·64bits` is similar: 55 M blocks, 17.8 k distinct
  scales (3.2e-4).
- **Within-buffer sharing is even tighter than across-buffer sharing.**
  `mean_per_buffer_scale_share` is below 0.05 for the dominant 64-bit
  workloads (cam4, roms, pop2, namd, wrf, blender, fotonik, parest,
  xz, lbm). A typical buffer in those workloads has *one* scale that
  applies to almost every block — per-block scale overhead is in
  practice per-buffer.
- **The exceptions are small or single-buffer benches.** `omnetpp·64bits`
  (42 blocks, 42 scales, ratio 1.0), `imagick·32bits`
  (1 block, 1 scale), `nab·32bits` (167 blocks, 69 scales) — all
  edge cases with too little snapshot volume for the sharing pattern
  to develop. `povray·64bits` (mean per-buffer share 0.95) is the
  one production-volume case where per-block scales are mostly
  distinct.
- **Combine with Q14/Q19.** Q14 says every block fits the MXFP8
  spread budget (lossless); Q19 says block size doesn't matter for
  that fit. Q28 closes the loop: of the per-block scales we *do* have
  to emit, almost all are duplicates and the scale page costs much
  less than the textbook "one scale per block" overhead suggests.
- **Implication for compressed-LLC / on-chip MX storage.** The scale
  page is a strong candidate for run-length encoding, dictionary
  compression, or a per-row scale page (one scale per allocation
  rather than per block) on these workloads. The textbook MX overhead
  of `bits_per_block / N + 8 / N` (E8M0 scale) overstates the actual
  on-disk / on-chip cost.
