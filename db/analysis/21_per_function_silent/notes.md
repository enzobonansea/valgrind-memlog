# 21_per_function_silent — silent-store rate per allocation-site function

## What the experiment measures

Q09 reports the silent-store rate aggregated to `(bench, alloc_type)`.
That aggregate hides per-function structure: the paper's Table 2
headline ("CAM4's 4.8% aggregate hides 49.8% in `dyn_run`") is the
canonical example. This query reproduces the same silent-store
definition — a write that puts back the value already at
`(alloc_addr, generation, offset)`, detected via `LAG(value)
PARTITION BY alloc_addr, generation, offset ORDER BY rn` — and groups
by **allocation site** (the first non-allocator stack frame, same
skip-list as Q13 and Q16).

The query keeps the top-20 sites per bench ranked by `pairs` (stores
that had a previous neighbour at the same offset), with the additional
`HAVING SUM(pairs) >= 1000` floor to drop rare sites whose silent rate
would be statistically meaningless.

## result.csv

187 rows, one per `(bench, site)`. Columns: `stores`, `pairs`,
`silent`, `silent_frac` (= `silent / pairs`).

Per-bench coverage: `cam4`, `wrf`, `roms`, `pop2` carry the full
top-20; many smaller benches (e.g. `cactus` 2 sites, `gcc` 4 sites)
have fewer sites that clear the 1000-pair floor.

## figure.svg

Scatter, x = `pairs` (log), y = `silent_frac`. One dot per
`(bench, site)`. Marker size scales with `stores` (heavier sites pop).
Each bench has its own turbo colour; the legend sits on the right.

Callouts label the dozen highest `stores × silent_frac` points — the
sites where silent-store elimination would remove the most absolute
write volume (not just the highest rate). Dashed reference lines at
0.25, 0.5, 0.75 give a quick read of the silent-rate band.

How to read it: a dense vertical column at high-x means a bench has a
heavy-pair function. Where that column lands on the y-axis matters.
A dot in the top-right quadrant (`high pairs`, `high silent_frac`) is
worth optimising; a dot in the bottom-right is heavy traffic that
*can't* be silenced.

## Headline observations

- **Bench-level silent rates routinely hide per-function extremes.**
  `cam4`'s aggregate (Q09 64bits = 16.2%) hides
  `__m_attrvect_MOD_init_` at 68%, `__tp_core_MOD_fyppm` at 63%,
  `__alloc_mod_MOD_alloc_check_1d_double` at 53%; meanwhile
  `cd_core_` (the largest single site, 220 M pairs) sits at 2.3%.
  The overall bench rate is the volume-weighted average.
- **A handful of high-volume sites are essentially silent.**
  `bwaves · shell_` (958 M pairs, 53.2%), `cactus ·
  PUGH_EnableGArrayDataStorage` (300 M pairs, 33.2%),
  `wrf · solve_em_`-class sites occupy the top-right quadrant —
  these are the most lucrative targets in absolute terms.
- **Some benches are uniformly silent at the function level.**
  `deepsjeng · alloc_hash()` is the bench's only top-site, 86%
  silent at 116 M pairs. Same shape for `perlbench` object traffic
  (94% in `Perl_safesysmalloc`-class sites) and `xz · object`
  (~18% but on the bench's only large site — its only optimisable
  surface).
- **Some big functions are essentially un-silenceable.**
  `cam4 · cd_core_` (2.3%), `cam4 · __sw_core_MOD_d_sw` (0%),
  `blender · do_display_buffer_apply_thread` (0.05%),
  `cam4 · __sw_core_MOD_c_sw` (1.8%). These functions overwrite
  every byte they touch with new data — the buffer state matters
  for their semantics.
- The top-right quadrant is sparse but non-empty — there are
  function-grain wins available, particularly on `cam4`, `bwaves`,
  `pop2`, `wrf`, `cactus`, and `deepsjeng`. Q16
  (`alloc_site_profile`) provides the orthogonal view: which sites
  *receive* the most stores in absolute terms.
