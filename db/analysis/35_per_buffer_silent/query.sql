-- @set threads 1
-- @set memory_limit 32GB
-- @set watch_spill_gb 200
-- Silent-store rate per individual buffer (alloc_addr, generation).
-- Same silent-store definition as 09_silent_stores — a write that puts
-- back the value already at (alloc_addr, generation, offset) — but kept
-- at buffer granularity instead of aggregating to alloc_type. Backs the
-- paper figure showing how the silent rate varies *between buffers of
-- the same benchmark*, which the per-(bench, alloc_type) view averages
-- away.
--
-- Shape follows 21_per_function_silent: the LAG window carries only
-- narrow columns (carrying strings through the window blew the spill
-- budget on bwaves), buffer metadata (alloc_type, alloc_size) is joined
-- back from a tiny per-(alloc_addr, generation) lookup afterwards.
-- Per-bench iteration bounds the window state to one parquet at a time;
-- ORDER BY uses the view's `rn` column (parquet file_row_number).
WITH lagged AS (
    SELECT
        alloc_addr, generation, value,
        LAG(value) OVER (
            PARTITION BY alloc_addr, generation, "offset"
            ORDER BY rn) AS prev_value
    FROM {bench}
),
per_addr AS (
    SELECT
        alloc_addr, generation,
        COUNT(*)::BIGINT                                              AS stores,
        COUNT(*) FILTER (WHERE prev_value IS NOT NULL)::BIGINT        AS pairs,
        COUNT(*) FILTER (WHERE prev_value = value)::BIGINT            AS silent
    FROM lagged
    GROUP BY alloc_addr, generation
),
addr_meta AS (
    SELECT alloc_addr, generation,
           any_value(alloc_type) AS alloc_type,
           any_value(alloc_size) AS alloc_size
    FROM {bench}
    GROUP BY alloc_addr, generation
)
SELECT
    '{bench}'                                  AS bench,
    printf('0x%x', p.alloc_addr)               AS addr,
    p.generation,
    m.alloc_type,
    m.alloc_size,
    p.stores,
    p.pairs,
    p.silent,
    p.silent::DOUBLE / NULLIF(p.pairs, 0)      AS silent_frac
FROM per_addr p
JOIN addr_meta m USING (alloc_addr, generation)
WHERE p.pairs > 0
ORDER BY p.pairs DESC;
