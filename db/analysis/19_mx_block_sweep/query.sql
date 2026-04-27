-- MX (microscaling) viability across block sizes — sweep extension of 14.
-- Choosing a block size is the central design trade-off in MX formats:
-- larger blocks amortise the shared-scale overhead but tolerate less
-- exponent spread before underflow / overflow inside the block. This query
-- evaluates the same workload at block sizes {8, 16, 32, 64, 128} so the
-- viability vs. block-size curve can be plotted per benchmark.
--
-- Threshold of 8 matches MXFP8 (E4M3); we also report viability at spread
-- <= 4 (a hypothetical MXFP4-friendly threshold).
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
    CROSS JOIN (VALUES (8), (16), (32), (64), (128)) AS sz(block_size)
),
exped AS (
    SELECT bench, alloc_type, alloc_addr, generation, block_size,
        idx / block_size AS block_id,
        CASE
            WHEN value = 0 THEN NULL
            WHEN alloc_type = '64bits'
                AND ((value >> 52) & 2047) IN (0, 2047) THEN NULL
            WHEN alloc_type = '32bits'
                AND ((value >> 23) & 255)  IN (0, 255)  THEN NULL
            WHEN alloc_type = '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN alloc_type = '32bits' THEN ((value >> 23) & 255)::INT
        END AS exp_bits
    FROM expanded
),
spreads AS (
    SELECT bench, alloc_type, block_size, alloc_addr, generation, block_id,
        MAX(exp_bits) - MIN(exp_bits) AS spread,
        COUNT(exp_bits)               AS valid_n
    FROM exped
    GROUP BY bench, alloc_type, block_size, alloc_addr, generation, block_id
)
SELECT
    bench, alloc_type, block_size,
    COUNT(*)::BIGINT                                          AS blocks,
    SUM(valid_n < 2 OR spread <= 4)::DOUBLE
        / NULLIF(COUNT(*), 0)                                 AS viable_spread4,
    SUM(valid_n < 2 OR spread <= 8)::DOUBLE
        / NULLIF(COUNT(*), 0)                                 AS viable_spread8,
    AVG(spread) FILTER (WHERE valid_n >= 2)                   AS mean_spread
FROM spreads
GROUP BY bench, alloc_type, block_size
ORDER BY bench, alloc_type, block_size;
