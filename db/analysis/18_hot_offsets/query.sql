-- @set threads 2
-- Top hot offsets within the heaviest buffers (paper hot_offsets_* figs).
-- For each benchmark, picks the 10 buffers with the most stores; for each
-- of those, lists the 5 most-written byte offsets and their share of the
-- buffer's writes.
--
-- Pairs naturally with 17_intra_buffer_gini.sql (which summarises how
-- skewed the within-buffer distribution is): this query shows where the
-- skew actually lives.
--
-- Per-bench iteration so the per-(buffer, offset) hash agg stays bounded
-- by one bench at a time. Single pass over {bench}: aggregate per
-- (alloc_addr, generation, offset), derive per-buffer totals via window,
-- then pick top-10 buffers × top-5 offsets — avoids the previous pattern's
-- second pass + JOIN back to all_stores.
WITH per_offset AS (
    SELECT alloc_addr, generation, "offset",
        any_value(alloc_type) AS alloc_type,
        any_value(alloc_size) AS alloc_size,
        COUNT(*)              AS writes
    FROM {bench}
    GROUP BY alloc_addr, generation, "offset"
),
buffer_totals AS (
    SELECT *,
        SUM(writes) OVER (PARTITION BY alloc_addr, generation) AS buffer_stores,
        SUM(writes) OVER ()                                    AS bench_total
    FROM per_offset
),
top_buffers AS (
    SELECT alloc_addr, generation, buffer_stores
    FROM (
        SELECT DISTINCT alloc_addr, generation, buffer_stores
        FROM buffer_totals
    )
    ORDER BY buffer_stores DESC
    LIMIT 10
),
ranked AS (
    SELECT bt.*,
        ROW_NUMBER() OVER (
            PARTITION BY bt.alloc_addr, bt.generation
            ORDER BY writes DESC) AS off_rnk
    FROM buffer_totals bt
    JOIN top_buffers USING (alloc_addr, generation)
)
SELECT
    '{bench}' AS bench,
    printf('0x%x', alloc_addr)                  AS addr,
    generation,
    alloc_type,
    alloc_size,
    "offset",
    writes,
    100.0 * writes / NULLIF(buffer_stores, 0)   AS pct_of_buffer,
    100.0 * writes / NULLIF(bench_total, 0)     AS pct_of_bench
FROM ranked
WHERE off_rnk <= 5
ORDER BY buffer_stores DESC, off_rnk;
