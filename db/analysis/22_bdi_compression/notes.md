# 22_bdi_compression — BDI cache-line compressibility per (bench, alloc_type)

## What the experiment measures

BDI (Base+Delta Immediate, Pekhimenko et al. 2012) partitions a
64-byte cache line into elements, picks one as a base, and stores the
rest as fixed-width signed deltas relative to the base. A line is
*compressible at delta-width K* when the range of element values
inside the line fits in K bits.

Operating on the **last-write snapshot** per
`(alloc_addr, generation, offset)`, we group offsets into 64-byte
cache lines (`offset // 64`) and report the fraction of lines whose
value range (`MAX − MIN`) fits in a K-bit signed delta for K ∈ {8, 16,
32}. A line with one populated slot (`slots = 1`) is trivially
compressible and tracked separately as `trivial_lines`. The `bdiK_frac`
columns use *only multi-slot lines* in the denominator
(`COUNT(*) FILTER (WHERE slots >= 2)`).

`mean_range` is the average value range of multi-slot lines (in the
raw integer interpretation of the bytes — useful as a sanity-check;
huge values mean a few outlier lines dominate the mean).

## result.csv

44 rows, one per `(bench, alloc_type)` (32-bit and 64-bit alignment).
Columns: `lines`, `trivial_lines`, `bdi8_frac`, `bdi16_frac`,
`bdi32_frac`, `mean_range`.

By construction `bdi8_frac ≤ bdi16_frac ≤ bdi32_frac`. A row whose
`bdi8_frac` already equals `bdi32_frac` is purely bimodal — every
compressible line fits in 8 bits, the rest don't fit in 32.

## figure.svg

Heatmap, rows = `(bench · alloc_type)` (alphabetical), columns =
`{single-slot share, BDI-8, BDI-16, BDI-32}`. Cell colour and label =
percentage on the standard `soft_rdylgn` ramp (orange → yellow →
green); `vmin=0, vmax=1`. Empty cells render as `—`.

The first column (`single-slot`) is the share of lines with only one
populated offset — these are trivially compressible but tell a
different story (sparse buffer touches, e.g. `xz · 64bits` is 47%
single-slot). The next three columns show how compressibility
*tightens* as the delta budget shrinks.

## Headline observations

- **32-bit-aligned snapshots are highly BDI-compressible.**
  `fotonik · 32bits` 99% / 99% / 100%, `pop2 · 32bits` 74% / 90% /
  95%, `roms · 32bits` 93% / 93% / 99%, `wrf · 32bits` 32% / 39% /
  100%. Most 32-bit lines hold values that fit into a small range —
  consistent with structured arrays of floats sharing a tight
  exponent.
- **64-bit-aligned snapshots are dramatically less BDI-friendly.**
  `bwaves · 64bits` 18%, `cam4 · 64bits` 11%, `lbm · 64bits` 17%,
  `xz · 64bits` 6% — even at the loosest 32-bit delta budget. BDI
  was designed for integer/pointer values; 64-bit IEEE-754 floats
  share their exponent and sign at the high end of the word but
  differ in the low mantissa, so the *range* of the raw integer
  interpretation is enormous (`mean_range` ≈ 10¹⁸ for several rows).
- **A few benches stay highly compressible at 64 bits.**
  `fotonik · 64bits` 99.3% across the board, `gcc · 64bits` jumps
  51% → 57% → 100%, `omnetpp · 64bits` 3% / 67% / 99.9%. These are
  lines dominated by zeros, pointers in a small heap range, or
  small integers padded to 8 bytes.
- **`trivial_lines` is a separate signal.** `xz · 64bits` 47%
  single-slot tells us almost half its lines have only one populated
  offset — the buffer is being touched sparsely, not densely.
  Single-slot lines are trivially compressible in any line-level
  scheme (just store the one value).
- BDI's caveat (Q22 query header): the metric overestimates
  compressibility for arrays of small magnitudes (high bits agree
  trivially) and underestimates for arrays sharing an exponent but
  differing in the low mantissa. Q23 (`23_fpc_patterns`) adds the
  float-pattern-aware view.
