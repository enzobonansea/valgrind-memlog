# 35_per_buffer_silent — silent-store rate per (bench, buffer)

## What the experiment measures

Same silent-store definition as `09_silent_stores` — a store whose value
is bit-identical to the most recent prior write at the same
`(alloc_addr, generation, offset)` — but the rate is kept at the
granularity of the individual buffer `(alloc_addr, generation)` instead
of being aggregated to `(bench, alloc_type)`. This is the distribution
that Q09's three-panel view averages away: how much the silent rate
varies *between buffers of the same benchmark*.

## result.csv

One row per `(bench, addr, generation)` with `pairs > 0`
(224,455 rows, 24 benches, 15.16 B pairs total):

- `addr`, `generation` — buffer identity; `alloc_type`, `alloc_size` — metadata.
- `stores` — all stores into the buffer.
- `pairs` — stores at a location with at least one earlier store
  (denominator; same meaning as Q09's `stores_with_prev`).
- `silent` — of those, how many re-wrote the same bits.
- `silent_frac` — `silent / pairs`.

wrf was computed in 6 exact hash-partitioned passes
(`hash(alloc_addr) % 6`) because its single-pass window sort spilled
past the host disk; an `alloc_addr` filter never splits a LAG partition,
so the union of the passes is identical to a single pass.

## figure.svg

One horizontal strip per benchmark (sorted by volume-weighted aggregate,
highest at top). One dot per buffer at its `silent_frac`, vertically
jittered; dot area grows with `log10(pairs)`; colour is the buffer's
`alloc_type` (Wong palette, same colours as Q09). The black tick is the
benchmark's pairs-weighted aggregate — the single number the
per-(bench, alloc_type) view reports. Dots are the top 400 buffers per
bench with `pairs ≥ 1000` (a bench whose every buffer is below the
floor keeps all its buffers); the right margin reports
`plotted/total · % of the bench's pairs covered`. Plotted dots carry
83.5 % of the suite's pairs.

## Headline observations

- **The benchmark aggregate is a volume-weighted average over buffers
  that mostly do not resemble it.** Suite-wide, only 22 % of
  silent-eligible pairs live in buffers whose silent rate is within
  ±5 points of their own benchmark's aggregate.
- **wrf** (aggregate 26 %) is the clearest case: 54 % of its pairs sit
  in buffers that are <5 % silent, 8 % in buffers >95 % silent, and the
  bulk of the rest in a 0.55–0.80 band — the aggregate falls in a gap
  where almost no actual buffer lives.
- **cam4** (17 %) and **roms** (19 %): >50 % of pairs in near-zero-silent
  buffers, with a long tail of buffers spanning the full [0, 1] range.
- **blender** (50 %) is bimodal at the buffer level: 33 % of pairs in
  <5 %-silent buffers and 28 % in >95 %-silent buffers; the 50 %
  aggregate describes almost nothing (2 % of pairs within ±5 pp).
- The degenerate rows are honest: **namd** and **omnetpp** really are
  uniformly non-silent (aggregate ≤1 %, ~100 % of pairs in <5 % buffers),
  and **fotonik** really is uniformly silent (99.6 %). **cactus** is the
  rare mid-rate bench where the aggregate is representative (79 % of
  pairs within ±5 pp of its 33 %).
- Per-buffer rates also cut across alloc_type: x264's 0.0–0.4 band mixes
  `object` and `32bits` buffers at every rate, so neither grouping
  (type or benchmark) predicts a buffer's behaviour.
