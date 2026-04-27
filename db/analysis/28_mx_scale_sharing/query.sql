-- MX scale-sharing efficiency: of all the per-block scales an MX encoder
-- would emit, how many are actually distinct? A low distinct-fraction
-- means many adjacent blocks share the same shared exponent and the
-- per-block scale page can be heavily compressed (e.g. by RLE or by
-- moving to a row-level scale).
--
-- 19_mx_block_sweep tells you whether each block fits within an exponent
-- spread; this query tells you how much *additional* savings come from
-- the regularity of the scales themselves. Together they answer the
-- question reviewers ask: "is per-block scale overhead amortizable in
-- practice on real workloads?"
--
-- For each (bench, alloc_type, block_size):
--   blocks                  total blocks across all snapshots
--   distinct_scales         distinct max-exponent values across blocks
--   scale_share_ratio       distinct_scales / blocks (low = compressible)
--   per_buffer_scale_share  mean within-buffer scale variety
--                           (0 = same scale for the whole buffer)
--
-- Citations: Rouhani 2023 NeurIPS (Shared Microexponents); OCP MX spec
-- v1.0; Hopper / Blackwell architecture white papers.
WITH numbered AS (
    SELECT *, ROW_NUMBER() OVER () AS rn
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits')
),
snapshot AS (
    SELECT bench, alloc_type, alloc_addr, generation, "offset", value
    FROM numbered
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY bench, alloc_addr, generation, "offset"
        ORDER BY rn DESC) = 1
),
indexed AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY bench, alloc_addr, generation
            ORDER BY "offset") - 1 AS idx
    FROM snapshot
),
expanded AS (
    SELECT i.*, sz.block_size
    FROM indexed i
    CROSS JOIN (VALUES (16), (32), (64)) AS sz(block_size)
),
blk_exp AS (
    SELECT bench, alloc_type, block_size, alloc_addr, generation,
        idx / block_size AS block_id,
        MAX(
            CASE
                WHEN value = 0 THEN NULL
                WHEN alloc_type = '64bits'
                    AND ((value >> 52) & 2047) IN (0, 2047) THEN NULL
                WHEN alloc_type = '32bits'
                    AND ((value >> 23) & 255)  IN (0, 255)  THEN NULL
                WHEN alloc_type = '64bits' THEN ((value >> 52) & 2047)::INT
                WHEN alloc_type = '32bits' THEN ((value >> 23) & 255)::INT
            END
        ) AS scale_exp
    FROM expanded
    GROUP BY bench, alloc_type, block_size, alloc_addr, generation, block_id
),
per_buffer AS (
    SELECT bench, alloc_type, block_size, alloc_addr, generation,
        COUNT(*)::BIGINT                               AS blocks,
        COUNT(DISTINCT scale_exp)::BIGINT              AS distinct_scales,
        COUNT(DISTINCT scale_exp)::DOUBLE
            / NULLIF(COUNT(*), 0)                      AS scale_share_ratio
    FROM blk_exp
    WHERE scale_exp IS NOT NULL
    GROUP BY bench, alloc_type, block_size, alloc_addr, generation
)
SELECT
    bench, alloc_type, block_size,
    SUM(blocks)::BIGINT                                AS blocks,
    SUM(distinct_scales)::BIGINT                       AS distinct_scales_total,
    SUM(distinct_scales)::DOUBLE / NULLIF(SUM(blocks), 0) AS overall_scale_share,
    AVG(scale_share_ratio)                             AS mean_per_buffer_scale_share,
    APPROX_QUANTILE(scale_share_ratio, 0.5)            AS median_per_buffer_scale_share
FROM per_buffer
GROUP BY bench, alloc_type, block_size
ORDER BY bench, alloc_type, block_size;
