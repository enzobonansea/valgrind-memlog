# 08_coverage — per-bench slot write density

`result.csv`: per (bench, alloc_type), the mean / min / max of
`unique_offsets * slot_bytes / alloc_size` (fraction of slots that ever
receive a store) plus mean writes per written slot.

`figure.svg`: two scatter panels, one per slot width (4-byte for `32bits`,
8-byte for `64bits`). Each dot is one bench.

## Axes
- **x — avg coverage**: of each allocation's slots, what fraction got at
  least one store. 0 = barely touched, 1 = every slot written.
- **y — avg writes per written slot (log)**: among the slots that *were*
  written, how many times each was overwritten on average. 1 = write-once,
  1000 = hammered repeatedly.
- **bubble size**: number of allocations behind that point (log scaled).

## Quadrants — the regime each bench is in
- **sparse poking** (bottom-left): a few slots touched, each barely
  rewritten. Looks like updating two struct fields inside a big object.
- **rewrite churn** (top-left): a small region of the allocation, but that
  region is pounded over and over. Scratch buffers, hot accumulators inside
  tight loops.
- **streaming / init** (bottom-right): the whole allocation is filled, each
  slot ~once. Zero-init, memcpy, building an output array end-to-end.
- **in-place update** (top-right): every slot touched *and* touched many
  times. Long-lived working arrays mutated in iterations (solver state,
  particle positions over timesteps).

## What to read from it
- Where the mass of large bubbles sits tells you the dominant access pattern
  at that slot width. E.g. `cam4` and `wrf` have huge 32-bit bubbles down in
  *streaming/init* — float arrays being filled. `mcf`, `namd`, `imagick`
  64-bit dots sit way up in *in-place update* — pointer/double arrays
  mutated repeatedly.
- If a bench appears in different regimes across the two panels, its
  int/float side and its pointer/double side are used for genuinely
  different things.
- A point near the right edge with low y is essentially write-once memory —
  a candidate for cheap allocation strategies. A point near the top,
  regardless of x, is the opposite: dominated by reuse, where allocator
  cost matters less than locality.

## Implementation
Per-bench iteration with two-stage GROUP BY (offset → alloc) so every
operator spills cleanly. `COUNT(DISTINCT "offset")` per
`(alloc_addr, generation)` does not spill, hence the rewrite.
