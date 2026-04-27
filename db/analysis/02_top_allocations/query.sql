-- Top 20 individual allocations per bench by store count — the buffers that
-- absorb the most store traffic.
--
-- Per-bench iteration: a global GROUP BY with COUNT(DISTINCT "offset") blew
-- past DuckDB's spill ceiling (the per-group distinct hash sets don't spill).
-- Running per bench bounds the hash table to one parquet's worth of allocs.
-- Two-stage GROUP BY keeps every operator spillable.
--
-- Global top-20 = top 20 of this CSV's `stores` column (provably exact: any
-- global top-20 row must be top-20 within its own bench).
WITH per_offset AS (
    SELECT
        alloc_addr, alloc_size, alloc_type, generation, "offset",
        COUNT(*) AS n
    FROM {bench}
    GROUP BY alloc_addr, alloc_size, alloc_type, generation, "offset"
)
SELECT
    '{bench}'                                           AS bench,
    printf('0x%x', alloc_addr)                          AS addr,
    alloc_size,
    alloc_type,
    generation,
    SUM(n)                                              AS stores,
    COUNT(*)                                            AS unique_offsets,
    ROUND(SUM(n) / NULLIF(alloc_size, 0)::DOUBLE, 2)    AS stores_per_byte
FROM per_offset
GROUP BY alloc_addr, alloc_size, alloc_type, generation
ORDER BY stores DESC
LIMIT 20;
