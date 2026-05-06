# 25_frequent_values — cumulative store coverage by top-K values

## What the experiment measures

Frequent-value compression (Yang 2000) and value-locality work
(Lipasti 1996) both rest on the assumption that a small dictionary of
the most-common values covers a large share of writes. This query
measures that directly. Per `(bench, alloc_type)` we count distinct
stored values, rank them by frequency (`ROW_NUMBER() OVER (PARTITION
BY alloc_type ORDER BY n DESC)`), and report the cumulative store
fraction covered by the top 1, 8, 64, 256 and 1024 values.

`top1_frac ≈ 0.5` means a single value (almost always `0`) accounts
for half the writes. `top64_frac → 1.0` means a 64-entry dictionary
suffices to compress the whole bench. A high `distinct_values` count
combined with a low `top1024_frac` means the bench has poor value
locality and dictionary compression won't help.

## result.csv

67 rows, one per `(bench, alloc_type)` with `alloc_type` ∈ {`32bits`,
`64bits`, `object`}. Columns: `total_stores`, `distinct_values`,
`top1_frac`, `top8_frac`, `top64_frac`, `top256_frac`, `top1024_frac`.

Reading the row left-to-right traces a cumulative coverage curve.
Reading the column down compares value-locality across benches.

## figure.svg

Three side-by-side panels (`32bits` / `64bits` / `object`). x-axis is
dictionary size (1, 8, 64, 256, 1024) on a log scale. y-axis is
cumulative store coverage `[0, 1]`. One line per benchmark
(turbo-coloured). Dashed reference lines at 50% and 90% give a quick
read of the saturation band.

A line that climbs sharply and saturates near 1.0 by x = 64 means
"this bench fits in a tiny value dictionary". A line that stays flat
near zero across the x-axis means "this bench has high value
diversity — every write is distinct".

## Headline observations

- **Object-alloc traffic is the most dictionary-compressible**, by
  far. Many object lines saturate above 95% by `top64`:
  `cactus · object` 100%, `fotonik · object` 99.9%,
  `mcf · object` 100%, `nab · object` 100%, `lbm · object` 100%,
  `omnetpp · object` 99.7%. Pointers and small-integer fields
  recur — frequent-value caches would be cheap and effective on
  object traffic.
- **`fotonik · 64bits` is the cleanest float case** — `top1` alone
  covers 99.3% (a single value, almost certainly 0) and `top8`
  reaches 99.8%. The rest of `fotonik`'s 64-bit pattern is
  essentially noise at the tail.
- **Several benches stay flat — high value diversity dominates.**
  `namd · 64bits` covers only 1.04% with 1024 values across 349 M
  distinct stored values — every doubleword is essentially unique.
  `omnetpp · 64bits` is similar (7.6%). `cam4 · 64bits` reaches
  18% — heavy traffic but mostly distinct mantissas. These are the
  workloads where dictionary compression is structurally
  uninteresting; bit-plane (Q29) or delta (Q20/Q22) approaches are
  the only avenues.
- **`top1` is dominated by zero**, but not always: `bwaves · 32bits`
  has `top1 = 0.75`, `imagick · 32bits` has `top1 = 0.99`. These
  are heavily-padded buffers where one specific non-zero constant
  recurs.
- **`distinct_values` is the orthogonal axis.** `wrf · 32bits` has
  765 M distinct values across 4.4 G stores — `top1024` covers only
  35%. `xz · 32bits` has 8 M distinct across 230 M stores —
  `top1024` is 17%. Both benches are dictionary-hostile despite
  having different distinct-count regimes.
- A small dictionary (`top64`) is enough to crack 90% on roughly
  one-third of the rows; a larger dictionary (`top1024`) buys
  comparatively little additional coverage on the remaining
  long-tailed benches. The ROI of dictionary expansion drops sharply
  past `top256`.
