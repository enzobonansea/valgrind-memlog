# Queries

All queries target the `all_stores` view that `tools/to_parquet.py` builds
in `db/memlog.duckdb` (one view per benchmark plus a UNION-ALL `all_stores`
view with a leading `bench` column).

Run any query with:

```bash
python3 -c "import duckdb; print(duckdb.connect('db/memlog.duckdb', read_only=True).execute(open('db/queries/01_summary.sql').read()).fetchdf().to_string(index=False))"
```

| # | File | What it answers |
|---|---|---|
| 01 | `01_summary.sql` | Per-benchmark totals: stores, distinct allocations, breakdown by `alloc_type`, fraction of zero-valued stores. |
| 02 | `02_top_allocations.sql` | The 20 individual `(alloc_addr, generation)` buffers that absorb the most stores, with stores-per-byte. |
| 03 | `03_size_distribution.sql` | Allocation-size histogram in power-of-two buckets per benchmark. |
| 04 | `04_hot_stack_sites.sql` | Top 15 allocation call sites grouped by the first 3 stack frames, ranked by stores absorbed. |
| 05 | `05_value_patterns.sql` | Counts of zero / pointer-shaped (top byte 0, magnitude > 2³²) / IEEE-754-double-shaped values per (bench, alloc_type). |
| 06 | `06_alignment.sql` | Store-offset alignment within allocations: 8-byte vs 4-byte-only vs unaligned counts. |
| 07 | `07_reused_allocations.sql` | The 20 heap addresses with the highest `generation` (most reused by the allocator). |
| 08 | `08_coverage.sql` | Mean / min / max fraction of an allocation's slots that ever receive a store, with average rewrites per slot. |
| 09 | `09_silent_stores.sql` | Stores that re-write the same value to the same `(alloc_addr, generation, offset)` as the previous store there — upper bound for silent-store elimination. |
| 10 | `10_bit_patterns.sql` | Per (bench, alloc_type): zero / zero-exponent / zero-mantissa counts, plus mean Hamming distance to the previous store within each allocation. |
| 11 | `11_write_concentration.sql` | Smallest N such that the top N buffers absorb 50 / 80 / 90 / 95 / 99 % of total stores per benchmark. |
| 12 | `12_format_feasibility.sql` | Fraction of stores losslessly representable in FP8 E4M3, FP8 E5M2, bfloat16, FP16, FP32 per (bench, alloc_type), via mantissa trailing-zero thresholds. |
| 13 | `13_per_function_feasibility.sql` | Same feasibility as 12 but grouped by the first non-allocator stack frame (paper Table 4 — `solve_em_` vs `surface_driver` style splits). |
| 14 | `14_mx_feasibility.sql` | Microscaling (MX) block viability: % of 32-element blocks (last-write snapshot) where the unbiased exponent spread is ≤ 8 (MXFP8). |
| 15 | `15_exponent_range.sql` | IEEE-754 exponent stats per (bench, alloc_type) plus share of values within FP8 E4M3 / E5M2 dynamic ranges. |
| 16 | `16_alloc_site_profile.sql` | Per allocation-site function: total stores, share of bench's writes, distinct buffers, mean allocation size, mean mantissa trailing zeros. |
| 17 | `17_intra_buffer_gini.sql` | Gini coefficient of writes-per-offset within each buffer, aggregated per (bench, alloc_type) (mean / median / min / max / write-weighted). |
| 18 | `18_hot_offsets.sql` | The 5 most-written byte offsets inside each of the top 10 buffers per benchmark, with their share of buffer and benchmark stores. |
| 19 | `19_mx_block_sweep.sql` | MX viability across block sizes {8, 16, 32, 64, 128} — the curve that justifies the block-size choice for MXFP4 / MXFP8 mappings. |
| 20 | `20_spatial_delta.sql` | Spatial value similarity between physically-adjacent offsets in the snapshot: bit-identical / 8-bit-delta / 16-bit-delta share + mean Hamming + mean log-delta. Direct measurement for delta-encoded compression. |
| 21 | `21_per_function_silent.sql` | Silent-store rate grouped by allocation-site function (backs the paper's "4.8% aggregate hides 49.8% in `dyn_run`" claim). |
| 22 | `22_bdi_compression.sql` | Per-cache-line BDI [Pekhimenko 2012] viability: % of 64-byte lines whose value range fits in 8 / 16 / 32-bit deltas. |
| 23 | `23_fpc_patterns.sql` | FPC [Burtscher 2009] pattern coverage: % of stores matching zero / sign-extended-{4,8,16,32} / high-zero-low16 / repeating-byte patterns, with the OR-union as an upper bound. |
| 24 | `24_required_exp_bits.sql` | Minimum exponent bit-width per allocation site to span its observed dynamic range — the FPVM "tiny floats" [HPDC '26] empirical question, answered per function. |
| 25 | `25_frequent_values.sql` | Cumulative fraction of stores covered by the top 1 / 8 / 64 / 256 / 1024 most-frequent values — direct measurement for frequent-value compression [Yang 2000]. |
| 26 | `26_outlier_channels.sql` | Per-allocation-site outlier-channel concentration: do extreme-magnitude stores live at a few stable offsets? Engages SmoothQuant / AWQ / QuIP [2023–2024]. |
| 27 | `27_per_offset_exponent_stability.sql` | Per-(site, offset) IEEE exponent variance — decides per-tensor vs per-channel vs per-token scaling for FP8 / MXFP4 [Microscaling 2023, OCP MX]. |
| 28 | `28_mx_scale_sharing.sql` | Distinct-shared-scale ratio across MX blocks of size {16, 32, 64} — quantifies the *amortizable* portion of per-block scale overhead. |
| 29 | `29_bit_plane_entropy.sql` | Per-bit Shannon entropy of stored values (all 64 positions) — predicts bit-plane compression ratios [Kim 2016, Mokey 2023]. |
| 30 | `30_posit_fit.sql` | Posit-32 suitability profile: share of values in the high-precision regime where posits beat IEEE-32 [Gustafson 2017, Klöwer 2020]. |
| 31 | `31_cacheline_homogeneity.sql` | 64-byte cache-line homogeneity (high-32, high-16, high-8 bits, biased exponent) — input for compressed-LLC designs [Touche, Buddy, Yacc]. |
| 32 | `32_validation_volume.sql` | Validation §3 — testing volume per benchmark: stores, distinct buffers, distinct call sites, distinct sizes, total bytes addressed. Empirical counterpart to the 11-test unit suite. |
| 33 | `33_validation_robustness.sql` | Validation §3 — robustness: per-benchmark spread of edge cases handled at SPEC scale (size span, max realloc generation, reused-buffer count, alignment classes, max offset). |
| 34 | `34_validation_correctness.sql` | Validation §3 — correctness: IEEE-754 binary64/binary32 exponent-class shares per (bench, alloc_type). Pathological capture would produce unphysical inf/NaN or exponent distributions. |

## Conventions

- **Ordering**: queries that need temporal store order (09, 10, 14) rely on
  `ROW_NUMBER() OVER ()` to reconstruct physical scan order; this is well
  defined here because `to_parquet.py` writes each
  `(alloc_addr, generation)`'s stores contiguously and in the order
  `parser.py` produced them.
- **Snapshot vs. all stores**: most queries operate on every store. Query
  14 (MX feasibility) operates on the *last-write snapshot* per
  `(alloc_addr, generation, offset)`, matching the paper's methodology.
- **Allocation site extraction** (queries 13, 16): the first stack frame
  whose function name doesn't match an allocator skip-list (`malloc`,
  `calloc`, `operator new`, `libgfortran`, `libstdc++`, `ld-2.`,
  `dl-init`, `???`, ...). Mirrors
  `papers/2026_Memlog/figs-generators/intra_buffer_analysis.py`.
- **Performance** (queries 13, 16): regex-based site extraction is applied
  *after* aggregating per `(bench, alloc_stack)` so it runs once per
  unique stack (dictionary-encoded in parquet) rather than once per store
  — orders of magnitude cheaper on the full dataset.
