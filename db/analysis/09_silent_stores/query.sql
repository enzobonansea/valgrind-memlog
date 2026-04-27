-- Silent stores: writes that put the same value back into the same
-- (alloc_addr, generation, offset) location as the most recent prior write.
-- Useful as an upper bound on how much store traffic a "silent-store
-- elimination" optimization could remove.
--
-- Per-bench iteration: a global ROW_NUMBER() OVER () followed by a
-- partitioned LAG over all_stores blew DuckDB's spill budget (the global
-- sort state grew unbounded). Running per bench bounds the window state
-- to one parquet at a time.
--
-- Ordering note: the parquet preserves the temporal order of stores within
-- each (alloc_addr, generation), because to_parquet.py emits .stores rows
-- in the same order parser.py wrote them. ROW_NUMBER() OVER () enumerates
-- in physical scan order, so PARTITION BY (alloc, gen, offset) ORDER BY rn
-- reconstructs the per-location store sequence within this bench.
WITH numbered AS (
    SELECT *, ROW_NUMBER() OVER () AS rn FROM {bench}
),
lagged AS (
    SELECT
        alloc_type, value,
        LAG(value) OVER (
            PARTITION BY alloc_addr, generation, "offset"
            ORDER BY rn
        ) AS prev_value
    FROM numbered
)
SELECT
    '{bench}'                                                        AS bench,
    alloc_type,
    COUNT(*) FILTER (WHERE prev_value IS NOT NULL)                   AS stores_with_prev,
    COUNT(*) FILTER (WHERE prev_value = value)                       AS silent,
    COUNT(*) FILTER (WHERE prev_value = value)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE prev_value IS NOT NULL), 0)  AS silent_frac
FROM lagged
GROUP BY alloc_type
ORDER BY alloc_type;
