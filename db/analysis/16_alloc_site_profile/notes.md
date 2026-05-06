# 16_alloc_site_profile — per-allocation-site write profile

## What the experiment measures

For every benchmark, ranks the top 15 allocation sites by total stores
absorbed. An *allocation site* is the first stack frame whose function
name doesn't match the allocator skip-list (`malloc`, `calloc`,
`realloc`, `free`, `operator new/delete`, `libgfortran`, `libstdc++`,
`ld-2.`, `dl-init`, `???`) — the same rule used by Q13 and by
`papers/2026_Memlog/figs-generators/intra_buffer_analysis.py`. Stores
are first collapsed per `(alloc_stack, alloc_addr, generation)` so the
expensive regex-based site extraction runs once per *unique stack*
(dictionary-encoded in parquet) rather than per store.

The query also reports a coarse precision proxy per site: the
write-weighted mean number of mantissa trailing zeros
(`mean_trailing_z`), measured over `32bits` and `64bits` stores. A site
with `mean_trailing_z ≈ 23` (or 52) sits in Q12's "mode B" — most
stored words are mantissa-zero. A site near 0 is mode A.

## result.csv

One row per `(bench, site)`, top 15 per bench. Columns: `stores`,
`pct_of_bench` (share of the bench's *displayed* top-15 total — see
caveat below), `buffers` (distinct `(alloc_addr, generation)` pairs at
that site), `mean_alloc_size` (write-weighted), `mean_trailing_z`. 221
rows.

Caveat: `pct_of_bench` is computed inside the top-15 window via
`100.0 * stores / SUM(stores) OVER ()`, so each bench's percentages
sum to ~100 across whatever the top-15 captured. Q11
(`11_write_concentration`) gives the corresponding tail (how many sites
absorb 50/80/90/95/99% of the bench's *total* writes).

## figure.svg

Stacked horizontal bar chart, one bar per bench, sorted top-to-bottom
by the dominant site's share. Each segment is one site; segments are
coloured by within-bench rank (viridis ramp, 1 = hottest). The dominant
site's name is overlaid on its segment when it's wide enough to fit. A
single bar means "one function dominates" — `cactus`'
`PUGH_EnableGArrayDataStorage` at ~99% reads as a near-monolithic
green band. A quilt of segments (`cam4`, `pop2`, `wrf`) means traffic
is spread across many sites. The colourbar is labelled `site rank
within bench (1 = hottest)`.

## Headline observations

- **Write traffic is heavily concentrated for some benches.** `cactus`
  is essentially one function (`PUGH_EnableGArrayDataStorage` ≈ 99.99%
  of its top-15 stores). `bwaves` is dominated by `shell_` (77%) and
  `bi_cgstab_block_` (22%). `blender` shows the cleanest "Pareto
  shape" with `zbuffer_solid` at 34% trailing into `render_result_new`
  21%, `zbufshadeDA_tile` 12%, `do_display_buffer_apply_thread` 7%,
  and a long tail.
- **`mean_trailing_z` is a fast precision smell-test per site.** In
  `blender`, `zbuffer_solid` (14.4) and `zbufshadeDA_tile` (14.2) are
  mode-B-leaning — these are the same sites Q13 shows at ~62% mode-B
  feasibility. `render_result_new` (4.4) and `_IO_file_doallocate`
  (0.0) are mode-A. The two extremes can sit in the same bench's
  top-five.
- **Buffer counts and mean sizes vary widely within a bench.**
  `blender · zbuffer_solid` has 2 430 buffers averaging ~18 KB each;
  `IMB_colormanagement_imbuf_for_write` is a single ~8 MB buffer
  absorbing 5.8% of writes. This shapes the design space: a few hot
  sites with many small buffers (cache-locality story) versus a
  handful of giant buffers (compression / streaming story).
