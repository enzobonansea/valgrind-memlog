# 31_cacheline_homogeneity — high-bit / exponent agreement per 64-byte line

## What the experiment measures

Compressed-cache designs (Touche, Buddy Compression, Yacc) fold a
64-byte line when its slots share their high bits — the line stores
one base prefix plus per-slot deltas. We test four prefix criteria
on each 64-byte aligned window of the snapshot:

- `homog_high32` — all slots share their upper 32 bits
- `homog_high16` — all slots share their upper 16 bits
- `homog_high8`  — all slots share their upper 8 bits
- `homog_exp`    — all slots share the IEEE-754 biased exponent
  (11 bits for `64bits`, 8 bits for `32bits`)

The high-K criteria are nested by construction
(`high32 ⊆ high16 ⊆ high8`): a line that agrees on 32 bits trivially
agrees on 16 and 8. `homog_exp` is independent of that chain — it
isolates the *float-aware* signal, since FPC- and posit-style line
compressors key on the exponent rather than the raw word.

## Snapshot semantics

The snapshot key is `(alloc_type, alloc_addr, offset)` — generation
is intentionally collapsed (see Q31's SQL header). For each physical
cell we keep the latest write across all reuses of that address. This
matches what a real cache compressor sees: a physical line holds
whatever was most recently written there, regardless of which logical
buffer owned it. Dropping generation cuts cam4 from ~700M cells
(OOM at 22 GB) to ~100M, comfortably inside the 22 GB cap.

The "homogeneous" predicate is `MIN(x) = MAX(x)` rather than
`COUNT(DISTINCT x) = 1`: O(1) state per group instead of a hash set,
which is what made bwaves and cam4 fit at all.

`mean_slots_per_line` is the average number of populated 8-byte slots
in lines with `slots ≥ 2` — close to 8 means the line is densely
written; far below 8 means the buffer touches it sparsely.

## result.csv

44 rows, one per `(bench, alloc_type)`. Columns: `lines` (multi-slot
line count, the denominator for `frac_homog_*`), `trivial_lines`
(single-slot lines — folded for free in any line-level scheme),
`mean_slots_per_line`, and the four `frac_homog_*` shares.

## figure.svg

Heatmap, rows = `(bench · alloc_type)` (alphabetical), columns =
`{single-slot share, high-32, high-16, high-8, IEEE exp}`. Cell
colour and label = percentage on the standard `soft_rdylgn` ramp
(orange → yellow → green); `vmin=0, vmax=1`. The single-slot column
divides by `lines + trivial_lines`; the four homogeneity columns use
the `lines` (multi-slot) denominator from the SQL.

## Headline observations

- **32-bit-aligned snapshots agree very strongly at the high-bit
  prefix.** `fotonik · 32bits` 100% / 100% / 100%, `wrf · 32bits`
  100% / 100% / 100%, `xz · 32bits` 100% across the board, `pop2 ·
  32bits` 100% / 100% / 100%. The 32-bit IEEE layout puts the sign +
  exponent + a few mantissa bits in the upper half of the 8-byte
  word, and same-buffer floats almost always share that range — a
  Touche-style line compressor wins on essentially every 32-bit row.
- **64-bit-aligned snapshots split sharply by workload.** Highly
  compressible: `fotonik · 64bits` 99% across the board, `omnetpp ·
  64bits` 100%, `xalancbmk · 64bits` 100%, `mcf · 64bits` 87% / 87%
  / 87% (small heap pointers). Resistant: `bwaves · 64bits` 5% / 5%
  / 5%, `blender · 64bits` 6% / 7% / 8%, `xz · 64bits` 7% / 7% / 7%.
  These are arrays of 64-bit floats whose top 32 bits already
  diverge across slots.
- **The exponent column rescues several 64-bit float workloads.**
  `cam4 · 64bits` jumps 31% → 41% → 74% → 54% (high-8 vs. exp), and
  `pop2 · 64bits` 75% → 77% → 83% → 80%. Exponent-aware encoders
  (FPC, posit, MX-shared scale) capture lines that look incompressible
  to a raw-bit base+delta because the mantissa LSBs differ.
- **`mcf · 32bits` is the canonical exp-poor row.** 68% / 68% / 68%
  / 0.005% — the high bits agree (small integers), but the
  "exponent" field of those bit-patterns interpreted as floats is
  garbage. Reminder that `homog_exp` is meaningful only for rows
  whose alloc_type is actually carrying floats (Q15, Q24, Q27).
- **`trivial_lines` is a separate signal.** `xz · 64bits` 510k
  single-slot lines vs. 404k multi-slot — over half the buffer is
  touched at one offset only. Single-slot lines are folded for free,
  so the "real" compressibility of xz at 64 bits is grimmer than the
  multi-slot 7% suggests, but the working set itself is sparser.
- This view complements Q22 (BDI raw-integer base+delta) and Q23
  (FPC float patterns): Q31 is the *line-level prefix* version of
  the question, which is what Touche / Buddy / Yacc actually key on.
