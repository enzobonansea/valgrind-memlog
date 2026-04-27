-- For each allocation, what fraction of its slots gets at least one store?
-- Slot size is 4 bytes for 32bits-aligned allocations, 8 bytes for 64bits.
-- Low coverage  => sparse writes (e.g. updating a few struct fields).
-- High coverage => dense streaming writes (e.g. zero-init, memcpy-style).
--
-- Per-bench iteration: COUNT(DISTINCT "offset") per (alloc_addr, generation)
-- doesn't spill. Two-stage GROUP BY (offset → alloc) keeps every operator
-- spillable.
WITH per_offset AS (
    SELECT
        alloc_addr, generation, alloc_size, alloc_type, "offset",
        COUNT(*) AS n
    FROM {bench}
    WHERE alloc_type IN ('64bits', '32bits')
    GROUP BY alloc_addr, generation, alloc_size, alloc_type, "offset"
),
per_alloc AS (
    SELECT
        alloc_addr,
        generation,
        ANY_VALUE(alloc_size) AS alloc_size,
        ANY_VALUE(alloc_type) AS alloc_type,
        COUNT(*)              AS unique_offsets,
        SUM(n)                AS stores
    FROM per_offset
    GROUP BY alloc_addr, generation
),
sized AS (
    SELECT
        *,
        CASE alloc_type WHEN '64bits' THEN 8 ELSE 4 END AS slot_bytes
    FROM per_alloc
)
SELECT
    '{bench}'                                                 AS bench,
    alloc_type,
    COUNT(*)                                                  AS allocations,
    AVG(unique_offsets * slot_bytes / alloc_size::DOUBLE)     AS avg_coverage,
    MIN(unique_offsets * slot_bytes / alloc_size::DOUBLE)     AS min_coverage,
    MAX(unique_offsets * slot_bytes / alloc_size::DOUBLE)     AS max_coverage,
    AVG(stores::DOUBLE / NULLIF(unique_offsets, 0))           AS avg_writes_per_slot
FROM sized
GROUP BY alloc_type
ORDER BY alloc_type;
