# 20_spatial_delta — adjacent-offset value similarity in the snapshot

## What the experiment measures

For each `(alloc_addr, generation)` we take the **last-write snapshot**
— the buffer's final byte pattern at every touched offset, computed via
`arg_max(value, rn)`. We then walk adjacent offsets in increasing order
and ask: how close is each value to its predecessor in the same buffer?
This is the **spatial** companion to Q09 and Q10, which measure
*temporal* similarity (consecutive stores at the same offset). Spatial
similarity is what delta-encoded compressors (BDI, FPC) and
structured-grid kernels exploit at the cache-line level.

For each pair, we record:

- `bit_identical` — the two adjacent values are byte-equal.
- `delta_le_8b` — their Hamming distance is ≤ 8 (an 8-bit XOR-delta
  would suffice).
- `delta_le_16b` — same, ≤ 16.
- `mean_hamming` — average Hamming distance per pair, masked to 32 or
  64 bits.
- `mean_log_delta` — average `ceil(log2(|val − prev_val| + 1))`. A
  proxy for the bit-width of the *additive* delta (relevant for
  arithmetic-difference encoders, not bitwise-XOR encoders).

Note that `bit_identical ⊂ delta_le_8b ⊂ delta_le_16b ⊂ pairs` —
the four shares stack cleanly.

## result.csv

44 rows, one per `(bench, alloc_type)` (32-bit and 64-bit alignment).
Columns: `pairs`, `bit_identical`, `delta_le_8b`, `delta_le_16b`,
`mean_hamming`, `mean_log_delta`.

## figure.svg

One row per `(bench · alloc_type)`, sorted alphabetically. Each row is
a stacked horizontal bar with four segments:

- dark green — `bit_identical / pairs`
- light green — `(delta_le_8b − bit_identical) / pairs` (small 8-bit
  XOR-delta sufficient)
- yellow — `(delta_le_16b − delta_le_8b) / pairs` (16-bit
  XOR-delta sufficient)
- orange — residual (delta exceeds 16 bits — full word would be
  needed)

The right margin annotates each row with `H=<mean_hamming>/<width>`
and `log₂Δ=<mean_log_delta>` so the bitwise and arithmetic delta
metrics live alongside the geometry.

## Headline observations

- **32-bit-aligned snapshots are highly delta-friendly.** `wrf · 32bits`
  is 96% within Hamming-16 (`827 M / 866 M` pairs); `pop2 · 32bits` is
  99%; `fotonik · 32bits` is 100%. A 16-bit-wide XOR-delta encoder
  would handle nearly every adjacent-offset pair losslessly on these
  workloads.
- **64-bit-aligned snapshots are noticeably harder.** `cam4 · 64bits`,
  `xz · 64bits` and `bwaves · 64bits` sit ≤ 35% within Hamming-16.
  Their `mean_hamming` lands around 20 / 64 — neighbours look much
  more like uncorrelated 64-bit values.
- **Bit-identical neighbours are common in zero-padded / sparse
  buffers.** `fotonik · 32bits` 94% bit-identical, `imagick · 32bits`
  99%, `roms · 32bits` 96%. These are buffers where adjacent slots
  store the same value (zeros, repeated constants, small scratch
  buffers).
- **Mean Hamming and mean log-delta tell complementary stories.**
  `blender · 64bits` H = 7.7 / 64 (good for XOR encoder) but
  log₂Δ = 53.8 (bad for arithmetic-delta encoder) — adjacent values
  share many bits but their numeric difference is huge. This pattern
  signals adjacent floats with different exponents but similar
  mantissas (sign bit + low mantissa bits aligned, exponent flips).
- This figure complements Q22 (BDI cache-line viability) and Q10
  (`bit_identical` *temporally*). Together they bracket the
  redundancy budget that line- or word-level compressors can target.
