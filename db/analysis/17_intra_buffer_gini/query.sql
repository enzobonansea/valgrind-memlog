-- Intra-buffer write concentration via the Gini coefficient (paper "Hot
-- Offsets" / Gini analysis).
--
-- For each buffer, count writes per offset and compute the Gini coefficient
-- of those counts:
--   G = (2 * Σ_i (i * x_i) - (n+1) * Σ x_i) / (n * Σ x_i)
-- where x_i is the i-th value in ascending sort and i ∈ [1..n].
-- G = 0 ⇒ uniform writes across all touched offsets (e.g. structured grid
-- update). G → 1 ⇒ all writes concentrated on a single offset (a hot
-- counter / scratch slot).
--
-- Aggregated per (bench, alloc_type) so the spread (mean / median / max)
-- summarises how concentrated intra-buffer write traffic tends to be.
-- Buffers with a single touched offset are excluded (Gini undefined).
--
-- Per-bench iteration so the per-offset hash agg stays bounded by one
-- bench's (alloc_addr, generation, offset) cardinality.
WITH per_offset AS (
    SELECT alloc_type, alloc_addr, generation, "offset",
        COUNT(*) AS writes
    FROM {bench}
    GROUP BY alloc_type, alloc_addr, generation, "offset"
),
ranked AS (
    SELECT alloc_type, alloc_addr, generation, writes,
        ROW_NUMBER() OVER (
            PARTITION BY alloc_addr, generation
            ORDER BY writes) AS i
    FROM per_offset
),
buf_gini AS (
    SELECT alloc_type, alloc_addr, generation,
        (2.0 * SUM(i * writes) - (COUNT(*) + 1) * SUM(writes))
            / NULLIF(COUNT(*) * SUM(writes), 0)         AS gini,
        COUNT(*)    AS n_offsets,
        SUM(writes) AS total_writes
    FROM ranked
    GROUP BY alloc_type, alloc_addr, generation
)
SELECT
    '{bench}' AS bench,
    alloc_type,
    COUNT(*)::BIGINT                                       AS buffers,
    AVG(gini)                                              AS mean_gini,
    QUANTILE_CONT(gini, 0.5)                             AS median_gini,
    MIN(gini)                                              AS min_gini,
    MAX(gini)                                              AS max_gini,
    -- write-weighted mean: heavier buffers count proportionally
    SUM(gini * total_writes) / NULLIF(SUM(total_writes), 0) AS write_weighted_gini
FROM buf_gini
WHERE n_offsets > 1
GROUP BY alloc_type
ORDER BY alloc_type;
