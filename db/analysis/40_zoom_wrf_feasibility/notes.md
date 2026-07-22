# 40_zoom_wrf_feasibility — wrf representability, individual buffers

## What the figure shows

A zoom into the single `wrf` row of `36_per_buffer_feasibility`, resolved
to **individual buffers**. Each row is one buffer — one
`(alloc_addr, generation)`, labelled `<addr>_<generation>` on the left —
and the dot sits at the fraction of its stores losslessly representable
in bfloat16 (mantissa trailing-zero criterion, Q12 thresholds), area
log-scaled in stores, colour = `alloc_type`. The right margin names the
allocating function. Rows are wrf's 22 heaviest buffers by stores, sorted
by representability; a stem connects each buffer to the dashed line
marking wrf's store-weighted benchmark aggregate (33%).

## Why one metric, not three panels

The parent figure uses three panels (FP8 E4M3 / bfloat16 / FP32). `wrf`
is a single-precision code: only 6 of its ~157k buffers are 64-bit, so
the FP32 demotion question does not apply, and the FP8/bfloat16/FP16
thresholds land within a few tenths of a percent of each other per buffer
(the Mode-B "all-or-nothing mantissa" story — a value's mantissa is
either fully zero or random-looking). Three panels would be three
near-identical columns. The variation that matters for `wrf` is between
buffers, so we show the single bfloat16 metric.

## Where the data comes from

No re-run of the feasibility pass. `result.csv` is
`36_per_buffer_feasibility/result.csv` (rows with `bench = wrf`) joined
to the same cheap `(alloc_addr, generation) -> alloc_stack` lookup as
`39_zoom_wrf_silent`, reduced to the first non-allocator frame.

## Headline observations

- wrf carries the most bfloat16-representable store volume in the suite
  (340 M stores), at a 33% benchmark aggregate. This zoom names the
  heaviest buffers behind it.
- The heaviest buffers span ~5% to ~89% representability, straddling the
  33% aggregate. `0xad27060_1` is 89% bfloat16-representable and
  `0x7927060_1` 58%, while equally heavy buffers sit near 5%. Only ~6% of
  wrf's stores sit in buffers near the aggregate.
- Buffers allocated by the *same* function
  (`alloc_space_field_core_0`) range from ~5% to ~60%: representability
  is a per-buffer property, exposed by binding each store to its buffer.
- Caveat inherited from Q12: `alloc_type` is alignment-derived, so a
  high-representability buffer can be integers or zeros reinterpreted as
  floats. This is an upper bound on lossless format reduction.
