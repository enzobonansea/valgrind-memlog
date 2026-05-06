# 09_silent_stores — silent-store rate per (bench, alloc_type)

## What the experiment measures

A *silent store* is a write whose value is bit-identical to the most recent
prior write at the same `(alloc_addr, generation, offset)`. For every store
in each bench's parquet we look up the previous store at the same byte
location (within the same allocation generation) using a `LAG(value) OVER
(PARTITION BY alloc_addr, generation, offset ORDER BY rn)` window, then
count matches. The fraction of matches is an upper bound on what
silent-store elimination could remove from the trace — dropping a write
that puts the same byte pattern back is, by construction, observationally
inert.

## result.csv

One row per `(bench, alloc_type)` where `alloc_type` ∈ {`32bits`, `64bits`,
`object`}. Columns:

- `stores_with_prev` — stores at a location that has at least one earlier
  store in this bench. Stores to a never-before-touched offset are
  excluded (the rate is undefined for them).
- `silent` — of those, how many re-wrote the same bits.
- `silent_frac` — `silent / stores_with_prev`. Empty when `stores_with_prev = 0`.

67 rows. Pairs where the bench never produced any 32-bit (or 64-bit, or
object) traffic appear as zero-row pairs.

## figure.svg

Heatmap, rows = bench, columns = alloc_type, cell colour = `silent_frac`
on a `[0, 1]` `soft_rdylgn` ramp (orange → yellow → green). Each cell
is annotated with the integer percentage; missing `(bench, alloc_type)`
combinations are left blank. The colourbar is labelled "% silent stores".

## Headline observations

- Silent-store rates are extremely **bimodal between alloc_types** within
  a bench. `blender` is 50% / 0.16% / 73% across 32/64/object;
  `xz` is 35% / 78% / 18%; `pop2` is 74% / 34% / 32%. There is no
  global "silent rate" — it lives at the alloc-type level.
- A handful of (bench, alloc_type) pairs sit at near-saturation:
  `fotonik · 64bits` 99.7%, `imagick · 64bits` 98.9%, `povray · object`
  97.9%, `perlbench · object` 94.3%, `deepsjeng · object` 85.8%,
  `nab · 32bits` 84.8%, `lbm · 64bits` 80.3%. These are the buffers
  that look most like idempotent scratchpads.
- A handful are essentially noise-free: `parest · 32bits` 0.0016%,
  `namd · 32bits` 0.0%, `namd · 64bits` 0.28%, `omnetpp · 32bits` 0.0%.
  Every store there carries new information.
- The aggregate per-bench rate hides per-function structure. Q21
  (`21_per_function_silent`) drills into the same trace by allocation
  site and shows that, e.g., `cam4`'s ~16% aggregate hides functions at
  >60% silent rate.
