# 39_zoom_wrf_silent — wrf silent-store rate, individual buffers

## What the figure shows

A zoom into the single `wrf` row of `35_per_buffer_silent`, resolved to
**individual buffers**. Each row is one buffer — one
`(alloc_addr, generation)`, labelled `<addr>_<generation>` on the left —
and the dot sits at that buffer's silent-store fraction, area log-scaled
in silent-eligible pairs, colour = `alloc_type`. The right margin names
the function that allocated the buffer (first non-allocator stack frame,
`..._MOD_` module prefix dropped). Rows are wrf's 22 heaviest buffers by
pairs, sorted by silent fraction; a stem connects each buffer to the
dashed line marking wrf's pair-weighted benchmark aggregate (26%).

## Where the data comes from

No re-run of the silent-store pass. `result.csv` is
`35_per_buffer_silent/result.csv` (rows with `bench = wrf`) joined to a
cheap `(alloc_addr, generation) -> alloc_stack` lookup (a bare `GROUP BY`,
no `LAG` window) and reduced to the first non-allocator frame with the
same regex as `21_per_function_silent`.

## Headline observations

- wrf is the suite's largest silent-store source: 939.7 M silent stores,
  26% benchmark aggregate. This zoom names the heaviest buffers behind it.
- The heaviest buffers span the full 0-to-1 range. `0xad27060_1` is
  silent 86% of the time and `0x7927060_1` 60%, while a dozen equally
  heavy buffers sit below 5%. Almost none sit at the 26% aggregate — the
  single number the whole-suite strip reports for wrf.
- The split is not explained away by the allocation site: most of these
  heavy buffers were allocated by the *same* function
  (`alloc_space_field_core_0`), yet they range from 60% silent to under
  1%. Binding each store to its buffer is what exposes them as
  individually addressable targets rather than an averaged mass.
- wrf is single-precision, so every buffer is 32-bit; the one `object`
  buffer shown (`ncio_create`, ~39%) is I/O bookkeeping.
