# Plow status — pause point

Snapshot of the analysis pipeline as of the pause for the day.

## Counts

- 16 / 34 analyses have a `result.csv`
- 16 / 16 of those have a `figure.svg` and a `notes.md`
- 18 / 34 are queued for retry; the SQL is in place but has not produced a
  result.csv yet

## Done (16)

| #  | Analysis                              | Wall time | Notes |
|----|---------------------------------------|-----------|-------|
| 01 | summary                               | 137 s     | per-bench totals |
| 02 | top_allocations                       | 1191 s    | per-bench rewrite, two-stage GROUP BY |
| 03 | size_distribution                     | 89 s      | |
| 04 | hot_stack_sites                       | 2299 s    | global; 38 min |
| 05 | value_patterns                        | 183 s     | exact-partition rewrite |
| 06 | alignment                             | 163 s     | |
| 07 | reused_allocations                    | 98 s      | |
| 08 | coverage                              | 1286 s    | per-bench rewrite |
| 11 | write_concentration                   | 90 s      | |
| 12 | format_feasibility                    | 384 s     | |
| 15 | exponent_range                        | 289 s     | |
| 23 | fpc_patterns                          | 336 s     | |
| 29 | bit_plane_entropy                     | 1089 s    | |
| 30 | posit_fit                             | 189 s     | |
| 32 | validation_volume                     | 319 s     | |
| 33 | validation_robustness                 | 178 s     | |

## Pending — failure mode and retry plan

### A. Heavy window queries (need finer-grain isolation)

Q09, Q10, Q14, Q19, Q20, Q21, Q22, Q24, Q26, Q27, Q28, Q31 — all rely on
`ROW_NUMBER() OVER ()` + per-partition sort/LAG. Even per-bench, a single
heavy bench (cam4 / wrf) produces > 100 GB of spill and the watchdog cuts
in. Buffer-pool carryover across benches inside one Python process also
pushes the next bench into OS swap.

**Fix to try next**:
- Wrap the per-bench loop in a *subprocess* per bench (fresh DuckDB buffer
  pool, fresh OS RSS) so memory is fully released between benches.
- For wrf / cam4 specifically, drop `memory_limit` to 8 GB and `threads`
  to 1 in that subprocess so DuckDB spills more aggressively and never
  competes with OS swap.
- Optionally: for `LAG`-driven queries (Q09, Q10, Q20, Q21), keep the SQL
  per-bench but split the bench's parquet into row-range chunks so the
  PARTITION BY sort fits in a smaller working set.

### B. CPU-bound regex/aggregation (need more threads, not less memory)

Q13, Q16 — both run a `regexp_extract` over a single-thread aggregate of
`alloc_stack`. CPU-bound, not memory-bound; took 2 h+ each before the
1 h watchdog cut them. Memory was never above 25 GB; spill stayed at 0.

**Fix to try next**:
- For these two, run with `THREADS = 16` (or `nproc`), keep `memory_limit`
  at 16 GB. DuckDB will fan out the `regexp_extract` cleanly because the
  upstream aggregate is already group-by-(bench, alloc_stack).

### C. DuckDB OOM (DISTINCT-per-group state doesn't spill)

Q17, Q25 — failed at 14.9 / 14.9 GiB when DuckDB couldn't fit the per-group
state of `COUNT(DISTINCT ...)` in memory. This is the same wall Q02 / Q08
hit before the per-bench + two-stage rewrite.

**Fix to try next**: rewrite each like 02_top_allocations / 08_coverage —
per-bench iteration with a two-stage GROUP BY (deduplicate on the DISTINCT
key first, then aggregate).

### D. Just need a re-run (mechanical fix already landed)

- Q19 — `str.format` was choking on a literal `{8, 16, 32, 64, 128}` in a
  comment. Fixed in `db/run.py` (replace instead of format). Re-running
  should succeed.
- Q34 — DuckDB rejected `0xFFFFFFFF` literal. Replaced with the same
  `((1::UBIGINT << 32) - 1)` form Q10/Q20 use. Re-running should succeed.

## Harness state

- `db/run.py` — runs `db/analysis/<NN_name>/query.sql`, writes `result.csv`
  next to it. Per-query watchdog interrupts at any of:
  spill > 100 GB, free disk < 30 GB, swap > 7 GB, wall time > 1 h.
  Wipes `db/.duckdb_tmp/` between queries so disk accumulation is bounded.
- `db/progress.sh` — one-screen plow snapshot.
- Current settings: `MEMORY_LIMIT="16GB"`, `THREADS=4`. The next pass
  through the heavy/CPU-bound queries should override these per-query.

## Resume

```bash
cd /home/enzo/valgrind-memlog/db

# easy ones first (already-mechanically-fixed)
python3 run.py 19_mx_block_sweep
python3 run.py 34_validation_correctness

# then category C (DISTINCT rewrites — code change first)
# edit 17_intra_buffer_gini and 25_frequent_values for per-bench + two-stage
python3 run.py 17_intra_buffer_gini
python3 run.py 25_frequent_values

# category B (more threads in run.py first, or a one-shot env override)
THREADS=16 python3 run.py 13_per_function_feasibility
THREADS=16 python3 run.py 16_alloc_site_profile

# category A (subprocess-per-bench refactor first; biggest job)
# Q09, Q10, Q14, Q20, Q21, Q22, Q24, Q26, Q27, Q28, Q31
```
