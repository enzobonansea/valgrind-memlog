# 13_per_function_feasibility — per-function lossless reduced-precision feasibility

## What the experiment measures

The Q12 lossless-format-feasibility test, refined to **per allocation
site**. For every store we read the IEEE-754 mantissa (low 52 bits at
64-bit alignment, low 23 bits at 32-bit alignment) and count its trailing
zero bits. A store qualifies for a target format when its mantissa has at
least N trailing zeros, where N is the number of mantissa bits the target
drops:

| target    | drops (32-bit value) | drops (64-bit value) |
|-----------|---------------------:|---------------------:|
| FP8 E4M3  | 20                   | 49                   |
| FP8 E5M2  | 21                   | 50                   |
| bfloat16  | 16                   | 45                   |
| FP16      | 13                   | 42                   |
| FP32      | n/a (32-bit row)     | 29                   |

Stores are grouped by `(bench, alloc_type, site)`, where `site` is the
first stack frame whose function name doesn't match the allocator
skip-list (`malloc`, `calloc`, `realloc`, `free`, `operator new/delete`,
`libgfortran`, `libstdc++`, `ld-2.`, `dl-init`, `???`). The query keeps
sites with at least 1000 stores and the top 20 sites globally per bench;
the figure further trims to the top 5 per bench for legibility.

## result.csv

One row per `(bench, alloc_type, site)`. Columns: `total` (store count
for that site), `pct_fp8_e4m3`, `pct_fp8_e5m2`, `pct_bf16`, `pct_fp16`,
`pct_fp32`. `pct_fp32` is empty for 32-bit rows (a 32-bit value already
*is* FP32). 194 rows.

## figure.svg

Heatmap, one row per `(bench, alloc_type, site)`, columns = the five
target formats in increasing precision order. Cell colour and integer
label = percentage of stores in that row that meet the trailing-zero
threshold (same `soft_rdylgn` ramp as Q12). Empty cells (32-bit FP32)
render as `—` on a neutral grey. Faint white horizontal lines separate
benches. Pairs with the same colour scale and column order as Q12 — the
two figures should be read as a pair: Q12 = per `(bench, alloc_type)`,
Q13 = the same metric drilled into hot sites.

## Headline observations

- **Function-level mode-A vs mode-B is even sharper than at bench
  level.** `blender · 32bits · zbuffer_solid` is 62% mode-B across all
  formats; `render_result_new` (same bench, same alloc_type) is 18%.
  These are the same trace but very different functions.
- **Numerically-active hot sites read low across the row.**
  `cam4 · 64bits · __sw_core_MOD_c_sw` is 0.23% across every format —
  ~172 M stores whose mantissas are essentially never near-trivial.
  `cam4 · 64bits · cd_core_` is 4.5%. `bwaves · 64bits · flux_` jumps
  from 23% (FP8/bf16/FP16) to 49% (FP32), which is the cleanest
  staircase any function shows.
- **Tiny function tails sit at saturation.** `blender · 64bits ·
  RE_findOrAddVlak` (8 K stores) is 99.9% across every format and
  `add_memfilechunk` is 31% — both small bookkeeping sites whose
  stored doubles are mostly zero.
- The Q12 caveat applies here too: `alloc_type` is alignment-bucketed,
  not type-tagged, so a function dominated by integer or pointer
  stores will read very high in this heatmap (those words trivially
  pass any mantissa-trailing-zero test). The figure should be read as
  "share of byte patterns that *would* round-trip", not "share that is
  actually FP".
