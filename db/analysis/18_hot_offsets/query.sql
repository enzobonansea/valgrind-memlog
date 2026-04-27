-- Top hot offsets within the heaviest buffers (paper hot_offsets_* figs).
-- For each benchmark, picks the 10 buffers with the most stores; for each
-- of those, lists the 5 most-written byte offsets and their share of the
-- buffer's writes.
--
-- Pairs naturally with 17_intra_buffer_gini.sql (which summarises how
-- skewed the within-buffer distribution is): this query shows where the
-- skew actually lives.
WITH per_buffer AS (
    SELECT bench, alloc_addr, generation, alloc_size, alloc_type,
        COUNT(*) AS stores
    FROM all_stores
    GROUP BY bench, alloc_addr, generation, alloc_size, alloc_type
),
top_buffers AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY bench ORDER BY stores DESC) AS buf_rnk
    FROM per_buffer
    QUALIFY buf_rnk <= 10
),
per_offset AS (
    SELECT s.bench, s.alloc_addr, s.generation, s."offset",
        COUNT(*) AS writes,
        ANY_VALUE(tb.stores) AS buffer_stores,
        ANY_VALUE(tb.alloc_type) AS alloc_type,
        ANY_VALUE(tb.alloc_size) AS alloc_size
    FROM all_stores s
    JOIN top_buffers tb USING (bench, alloc_addr, generation)
    GROUP BY s.bench, s.alloc_addr, s.generation, s."offset"
),
ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY bench, alloc_addr, generation
            ORDER BY writes DESC) AS off_rnk,
        SUM(writes) OVER (PARTITION BY bench) AS bench_total
    FROM per_offset
)
SELECT
    bench,
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
ORDER BY bench, buffer_stores DESC, off_rnk;
