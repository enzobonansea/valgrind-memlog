-- Write concentration: how many top buffers (ranked by store count) absorb
-- each fraction of total stores, per benchmark.
--
-- "top_for_50pct" is the smallest N such that the N most-written buffers
-- cover >= 50% of all stores. Low N => extreme concentration (a few buffers
-- absorb most of the write traffic, classic for grid/array workloads).
-- High N => writes spread evenly across allocations.
--
-- Granularity: per (alloc_addr, generation) — a reused heap address counts
-- as separate buffers across its generations. See 02_top_allocations.sql for
-- the per-buffer detail and 07_reused_allocations.sql for reuse patterns.
WITH per_buffer AS (
    SELECT
        bench,
        alloc_addr,
        generation,
        COUNT(*) AS stores
    FROM all_stores
    GROUP BY bench, alloc_addr, generation
),
ranked AS (
    SELECT
        bench, stores,
        ROW_NUMBER() OVER (PARTITION BY bench ORDER BY stores DESC) AS rnk,
        SUM(stores) OVER (
            PARTITION BY bench ORDER BY stores DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cum_stores,
        SUM(stores) OVER (PARTITION BY bench) AS total_stores
    FROM per_buffer
)
SELECT
    bench,
    MAX(total_stores)::BIGINT                                              AS total_stores,
    COUNT(*)::BIGINT                                                       AS total_buffers,
    MIN(rnk) FILTER (WHERE cum_stores >= 0.50 * total_stores)              AS top_for_50pct,
    MIN(rnk) FILTER (WHERE cum_stores >= 0.80 * total_stores)              AS top_for_80pct,
    MIN(rnk) FILTER (WHERE cum_stores >= 0.90 * total_stores)              AS top_for_90pct,
    MIN(rnk) FILTER (WHERE cum_stores >= 0.95 * total_stores)              AS top_for_95pct,
    MIN(rnk) FILTER (WHERE cum_stores >= 0.99 * total_stores)              AS top_for_99pct
FROM ranked
GROUP BY bench
ORDER BY total_stores DESC;
