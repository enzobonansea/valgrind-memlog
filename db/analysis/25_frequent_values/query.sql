-- Frequent-value coverage per (bench, alloc_type) — direct measurement of
-- the assumption behind frequent-value compression [Yang 2000] and value
-- locality work [Lipasti 1996]. For each (bench, alloc_type) we count
-- distinct values, rank them by frequency, and report what cumulative
-- fraction of stores is covered by the top 1 / 8 / 64 / 256 / 1024
-- distinct values.
--
-- Interpretation:
--   top1_frac = 0.5      → a single value (likely 0) covers half the writes
--   top64_frac near 1.0  → a small dictionary suffices to compress the
--                          whole buffer (à la frequent-value caches)
--   distinct_values huge → low value locality, dictionary compression won't
--                          help
--
-- Per-bench iteration so the per-value hash agg stays bounded by one
-- bench's distinct-value cardinality (which can be hundreds of millions
-- on the bigger benches; running over all_stores at once spills hard).
WITH counts AS (
    SELECT alloc_type, value, COUNT(*) AS n
    FROM {bench}
    GROUP BY alloc_type, value
),
ranked AS (
    SELECT alloc_type, n,
        ROW_NUMBER() OVER (PARTITION BY alloc_type ORDER BY n DESC) AS rnk
    FROM counts
)
SELECT
    '{bench}' AS bench, alloc_type,
    SUM(n)::BIGINT                                                      AS total_stores,
    COUNT(*)::BIGINT                                                    AS distinct_values,
    SUM(n) FILTER (WHERE rnk = 1)::DOUBLE    / NULLIF(SUM(n), 0)        AS top1_frac,
    SUM(n) FILTER (WHERE rnk <= 8)::DOUBLE   / NULLIF(SUM(n), 0)        AS top8_frac,
    SUM(n) FILTER (WHERE rnk <= 64)::DOUBLE  / NULLIF(SUM(n), 0)        AS top64_frac,
    SUM(n) FILTER (WHERE rnk <= 256)::DOUBLE / NULLIF(SUM(n), 0)        AS top256_frac,
    SUM(n) FILTER (WHERE rnk <= 1024)::DOUBLE/ NULLIF(SUM(n), 0)        AS top1024_frac
FROM ranked
GROUP BY alloc_type
ORDER BY alloc_type;
