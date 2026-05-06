# 18_hot_offsets — top byte offsets inside each bench's heaviest buffers

## What the experiment measures

For every benchmark the query picks the **10 buffers** (`alloc_addr` ×
`generation`) with the most stores absorbed, and for each of those the
**5 most-written byte offsets**. The output therefore records up to 50
`(buffer, offset)` rows per bench — the actual hot spots inside the
hot buffers. Pairs naturally with Q17 (`17_intra_buffer_gini`), which
summarises *how* skewed the within-buffer distribution is; this query
shows *where* the skew lives.

The query computes per-`(alloc_addr, generation, offset)` write counts
in a single pass, then derives the buffer total via `SUM(writes)
OVER (PARTITION BY alloc_addr, generation)` and the bench total via
`SUM(writes) OVER ()` — avoiding a second scan.

## result.csv

1106 rows. Columns: `addr` (hex), `generation`, `alloc_type`,
`alloc_size`, `offset` (byte offset within the buffer), `writes`,
`pct_of_buffer` (the offset's share of its buffer's total writes),
`pct_of_bench` (the offset's share of the bench's total writes).

A row's `pct_of_buffer` is the right-tail signal: if it is large, that
single byte offset is a hot spot inside a hot buffer. `pct_of_bench`
indicates global importance — a hot offset inside a small buffer
might be locally dominant but globally tiny.

## figure.svg

One horizontal strip per bench. Each dot is a `(buffer, offset)` row.

- **x** — `pct_of_buffer`: how concentrated this offset is within its
  buffer.
- **size** — `√(pct_of_bench)`: heavier global contributors render
  larger.
- **colour** — within-bench buffer rank (viridis, 1 = darkest = the
  bench's hottest buffer).
- A small vertical jitter is applied so coincident dots don't fully
  overlap.
- The dominant offset of the heaviest buffer is annotated with
  `@<offset>` when its share is ≥5% of the buffer.

How to read it: a bench whose dots cluster near `x=0` has *uniform*
hot buffers — the writes spread evenly across many offsets (e.g.
big arrays, structured grids). A bench whose dots fan out toward the
right has hot buffers with **a few much-hotter offsets** — counters,
control fields, or per-loop scratch slots inside a larger allocation.

## Headline observations

- **`exchange2` is the cleanest hot-offset story** — multiple buffers
  show offsets at 20–45% of the buffer's writes (e.g. offset 56 alone
  takes 45% of buffer `0x4ed5dc0`). The bench is small, but every
  hot buffer has a few stable hot offsets.
- **`imagick` and `gcc` show within-buffer concentration in their
  heaviest buffers** — `imagick`'s top buffer has two offsets each at
  ~26% (`@13184` and `@28`); `gcc` has `@45416` / `@45424` at ~14%.
- **Most large benches are uniform within their hot buffers.**
  `blender`, `bwaves`, `cam4`, `wrf`, `roms`, `pop2` — the buffers
  with the most stores are big arrays whose top-5 offsets each take
  well under 1% of the buffer. These are streaming-array workloads,
  not counter-update workloads.
- **Buffer rank rarely correlates with offset concentration.** The
  darkest dots (bench's heaviest buffer) and lightest dots (rank-10)
  scatter along similar `pct_of_buffer` bands within a bench — the
  hot/uniform character is a property of the *bench's allocation
  style*, not of which buffer you're looking at.
- The complement to this view is Q17, where the per-buffer Ginis tell
  the same story aggregated. The two should be cross-referenced:
  Q17's `write_weighted_gini ≈ 0` rows correspond to clusters of
  dots near `x=0` here; high-weighted-Gini rows fan out.
