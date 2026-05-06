# 10_bit_patterns — bit-pattern composition and per-buffer Hamming coherence

## What the experiment measures

Per `(bench, alloc_type)` (restricted to `32bits` / `64bits` stores)
the query records, in a single scan over the bench's parquet, four
overlapping bit-pattern facts and one neighbour metric:

- `zero_values` — the value is exactly `0`.
- `exp_zero` — the IEEE-754 biased exponent field is `0` (the value is
  zero or a subnormal under a float reinterpretation).
- `mantissa_zero` — the mantissa bits are all `0` (the value is zero
  or an exact power of two under a float reinterpretation).
- `bit_identical` — the store wrote the same bits as the *previous
  store anywhere in the same buffer* (i.e. spatial coherence; not
  silent stores — those require the same offset and live in Q09).
- `mean_hamming` — average bit-difference between consecutive stores
  in the same buffer, masked to 32 or 64 bits as appropriate.

The neighbour facts are computed via a `LAG(value) OVER (PARTITION BY
alloc_addr, generation ORDER BY rn)` window, where `rn` is parquet's
file row number — the temporal store sequence within each
`(alloc_addr, generation)` is preserved by `to_parquet.py`.

## result.csv

44 rows, one per `(bench, alloc_type)` with `alloc_type` ∈ {`32bits`,
`64bits`}. Columns: `total`, `zero_values`, `exp_zero`,
`mantissa_zero`, `pairs` (stores with a previous neighbour),
`bit_identical`, `mean_hamming`.

The first three columns are not disjoint — every exact-zero satisfies
all three. They're reported separately because the gap between
`zero_values` and `exp_zero` measures subnormals, and the gap between
`exp_zero` and `mantissa_zero` measures non-zero exact-power-of-two
values. The hierarchy is `zero_values ≤ exp_zero ≤ mantissa_zero` for
floats, but on a trace this is alignment-bucketed (not type-tagged) so
small integers also satisfy `mantissa_zero` trivially.

## figure.svg

Two side-by-side panels (32-bit and 64-bit). Per panel, one row per
benchmark with four small horizontal bars, each in a Wong-palette
colour:

- dark blue — `zero_values / total`,
- light blue — `exp_zero / total`,
- orange — `mantissa_zero / total`,
- green — `bit_identical / pairs`.

The four bars overlap by construction; the figure shows the gaps
between them, which carry the information. The right margin annotates
each row with `H=<mean_hamming>/<bit-width>` so the spatial-coherence
metric stays out of the bar geometry.

## Headline observations

- **Mantissa-zero dominates exact-zero in most rows** — for many
  benches a small fraction of stores are *exactly* zero, but a much
  larger fraction have an all-zero mantissa under reinterpretation.
  E.g. `wrf · 32bits` is 31% exact-zero / 33% exp-zero / 32%
  mantissa-zero (close together — mostly zeros), but `pop2 · 32bits`
  is 24% / 98% / 24% (lots of subnormals as bytes, very few zeros)
  and `cam4 · 64bits` is 11% / 12% / 12% (zeros and subnormals only).
- **`bit_identical` is high wherever buffers store long runs of
  repeated values.** `fotonik · 64bits` is 99.8% bit-identical —
  successive stores within a buffer almost always carry the same
  bits. `xz · 64bits` and `parest · 32bits` are both ~64% (long runs
  of repeated 64-bit/32-bit constants).
- **Mean Hamming distance is the inverse signal.** `fotonik · 64bits`
  H = 0.05 (essentially identical neighbours), `parest · 32bits`
  H = 0.97. At the other extreme, `namd · 64bits` H = 28.3 / 64,
  `cam4 · 64bits` H = 21.2 / 64 — successive stores look near-random.
  These are the buffers least amenable to delta-style compression.
- **Spatial coherence is not the same as silent-store rate.** Q09
  asks "is the previous store at *this offset* the same?";
  Q10's `bit_identical` asks "is the previous store *anywhere in the
  buffer* the same?". Identical-fill buffers (e.g. zero-init regions)
  drive the latter without driving the former. The two columns give
  complementary upper bounds for redundancy-elimination schemes.
