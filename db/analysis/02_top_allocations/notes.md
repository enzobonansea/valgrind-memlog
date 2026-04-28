# 02_top_allocations — top 20 hottest buffers per bench

`result.csv`: ≤ 20 rows per bench (423 total). Columns: `addr`, `alloc_size`,
`alloc_type`, `generation`, `stores`, `unique_offsets`, `stores_per_byte`.
Per-bench view; the global top-20 across the whole suite is recoverable by
sorting the CSV by `stores` desc and slicing top 20 (provably exact: any
global-top-20 buffer is top-20 in its own bench).

`figure.svg`: cumulative-share line, one line per bench, x = top-K rank
(1..20), y = cumulative fraction of bench's total stores (Q01 denominator).
Reference line at 50%. Shows how concentrated store traffic is — for many
benches the top-K saturates above 70% well before K=20, motivating
per-allocation-site optimisation.

Implementation: per-bench iteration with two-stage GROUP BY (offset → alloc)
to keep `COUNT(DISTINCT "offset")` spillable in DuckDB.
