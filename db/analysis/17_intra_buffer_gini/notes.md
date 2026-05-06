# 17_intra_buffer_gini — Gini of per-offset writes within each buffer

## What the experiment measures

Within a single allocation buffer, do writes pile onto a few hot
offsets, or spread evenly across every touched slot? For each buffer
(`alloc_addr`, `generation`) we count writes per `offset`, then
compute the Gini coefficient of those counts:

```
G = (2 · Σ_i (i · x_i) − (n+1) · Σ x_i) / (n · Σ x_i)
```

where `x_i` is the i-th value in ascending sort and `i ∈ [1..n]`.
G = 0 means uniform writes across all touched offsets (e.g. a
structured-grid update); G → 1 means every write hits the same offset
(a hot counter / scratch slot). Buffers with a single touched offset
are excluded — Gini is undefined there.

Per-buffer Ginis are aggregated to `(bench, alloc_type)` granularity:
`min`, `median` (`approx_quantile`), `mean`, `max`, plus a
`write_weighted_gini` where buffers count proportionally to their
total write volume. The gap between unweighted `mean_gini` and
`write_weighted_gini` reveals whether the few high-traffic buffers
are more or less concentrated than the median buffer in the group.

## result.csv

67 rows, one per `(bench, alloc_type)`. Columns: `buffers` (number of
multi-offset buffers contributing), `mean_gini`, `median_gini`,
`min_gini`, `max_gini`, `write_weighted_gini`.

A handful of `xz` rows carry **numerical-overflow** values (G outside
`[0, 1]`, e.g. `xz · 64bits · max_gini = 64758.88`). The DuckDB
formula uses 32-bit ROW_NUMBER multiplied by writes — for the largest
buffers in `xz` that product overflows. The figure clips and flags
these rows; the underlying CSV preserves the raw values.

## figure.svg

One row per `(bench, alloc_type)`, sorted alphabetically. For each
row:

- a grey range bar from `min_gini` to `max_gini` with tick caps,
- a dark-blue vertical median tick,
- a filled blue dot for the unweighted `mean_gini`,
- an open orange ring for the `write_weighted_gini`.

The right-margin annotation shows `n=<buffers>`, with `⚠ overflow`
appended for the clipped `xz` rows. The legend (top, three columns)
identifies median / mean / write-weighted-mean.

The story the figure tells row-by-row: the **gap between the blue
dot and the orange ring**. When the orange ring is far to the right
of the blue dot (e.g. `cam4 · 32bits` 0.06 → 0.37, `omnetpp · 64bits`
0.007 → 0.76, `leela · 32bits` 0.002 → 0.50), the few heavy-traffic
buffers are *much more* concentrated than the buffer-mean — a
hot-offset story hiding inside a uniform-on-average bench. When the
ring sits left of the dot, the heavy buffers are *less* concentrated
than the average buffer.

## Headline observations

- **Most benches have median Gini ≈ 0** — within a typical buffer,
  writes are roughly uniform across touched offsets. This is the
  signature of grid sweeps and array updates: every slot sees about
  the same number of writes per pass.
- **Write-weighting shifts the picture sharply for several rows.**
  `cam4 · 32bits` and `omnetpp · 64bits` are nearly uniform on the
  buffer median but the bulk-traffic buffers are highly concentrated.
  These are the "one hot offset inside the big buffer" cases — the
  exact pattern Q18 (`18_hot_offsets`) localises.
- **A few rows are inherently spiky.** `mcf · 32bits` (single buffer
  at G = 0.79), `perlbench · 32bits` (write-weighted G = 0.96 across
  4 buffers), `namd · 32bits` (write-weighted G = 0.87). For these,
  the buffer's writes are dominated by one or two offsets — a
  counter, a head pointer, a per-loop scratch slot.
- **Object-alloc rows tend to be more uniform** than 32/64-bit rows
  — the `*_object` group is dominated by structured allocations
  (e.g. `namd · object` G ≈ 0.004 over 10 512 buffers), where every
  field gets touched roughly equally.
- The flagged overflow on `xz · 64bits` and `xz · object` is a known
  limitation of the current formula at scale; the surrounding rows
  remain reliable.
