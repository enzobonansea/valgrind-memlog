-- Validation: robustness — diversity of edge cases the tool handled at
-- SPEC scale. A single tool exercised across all rows of this table covers
-- the corners that the 11-test unit suite samples in isolation.
--
-- Columns:
--   min_size, median_size, max_size     allocation-size span actually seen
--   max_generation                      deepest realloc/reuse chain handled
--                                       on a single starting address
--   buffers_reused                      buffers with generation > 1
--                                       (proves rb-tree node replacement on
--                                        free/realloc fires correctly)
--   distinct_alignment_classes          how many of {64bits, 32bits, object}
--                                       appeared (alignment-handling breadth)
--   max_offset                          largest in-buffer offset stored at
--                                       (stresses offset arithmetic + buffer
--                                        correlation on large allocations)
WITH per_buf AS (
    SELECT
        bench,
        alloc_addr,
        generation,
        ANY_VALUE(alloc_size) AS sz,
        ANY_VALUE(alloc_type) AS atype,
        MAX("offset")         AS max_off
    FROM all_stores
    GROUP BY bench, alloc_addr, generation
),
per_addr AS (
    SELECT bench, alloc_addr, MAX(generation) AS max_gen
    FROM all_stores
    GROUP BY bench, alloc_addr
)
SELECT
    p.bench,
    MIN(p.sz)::BIGINT                                   AS min_size,
    QUANTILE_CONT(p.sz, 0.5)::BIGINT                  AS median_size,
    MAX(p.sz)::BIGINT                                   AS max_size,
    (SELECT MAX(max_gen) FROM per_addr a
       WHERE a.bench = p.bench)::BIGINT                 AS max_generation,
    (SELECT SUM(max_gen > 1)::BIGINT FROM per_addr a
       WHERE a.bench = p.bench)                         AS buffers_reused,
    COUNT(DISTINCT p.atype)::BIGINT                     AS distinct_alignment_classes,
    MAX(p.max_off)::BIGINT                              AS max_offset
FROM per_buf p
GROUP BY p.bench
ORDER BY p.bench;
