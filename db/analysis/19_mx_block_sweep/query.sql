-- MX (microscaling) viability across block sizes — sweep extension of 14.
-- Choosing a block size is the central design trade-off in MX formats:
-- larger blocks amortise the shared-scale overhead but tolerate less
-- exponent spread before underflow / overflow inside the block. This query
-- evaluates the same workload at block sizes {8, 16, 32, 64, 128} so the
-- viability vs. block-size curve can be plotted per benchmark.
--
-- Threshold of 8 matches MXFP8 (E4M3); we also report viability at spread
-- <= 4 (a hypothetical MXFP4-friendly threshold).
--
-- Per-bench iteration bounds window state to one parquet at a time.
-- Snapshot extraction uses arg_max(value, rn) (rn = parquet file_row_number
-- from the view) instead of the earlier ROW_NUMBER OVER () + QUALIFY
-- pattern. Block sizes are swept by aggregating five GROUP BYs and UNION
-- ALL'ing the results, rather than CROSS JOIN'ing rows by block size
-- (which 5×'d the input volume).
WITH snapshot AS (
    SELECT alloc_type, alloc_addr, generation, "offset",
        arg_max(value, rn) AS value
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
    GROUP BY alloc_type, alloc_addr, generation, "offset"
),
indexed AS (
    SELECT alloc_type, alloc_addr, generation,
        ROW_NUMBER() OVER (
            PARTITION BY alloc_addr, generation
            ORDER BY "offset") - 1 AS idx,
        CASE
            WHEN value = 0 THEN NULL
            WHEN alloc_type = '64bits'
                AND ((value >> 52) & 2047) IN (0, 2047) THEN NULL
            WHEN alloc_type = '32bits'
                AND ((value >> 23) & 255)  IN (0, 255)  THEN NULL
            WHEN alloc_type = '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN alloc_type = '32bits' THEN ((value >> 23) & 255)::INT
        END AS exp_bits
    FROM snapshot
),
spreads AS (
    SELECT alloc_type, 8 AS block_size, alloc_addr, generation, idx / 8 AS block_id,
        MAX(exp_bits) - MIN(exp_bits) AS spread, COUNT(exp_bits) AS valid_n
    FROM indexed
    GROUP BY alloc_type, alloc_addr, generation, idx / 8
    UNION ALL
    SELECT alloc_type, 16, alloc_addr, generation, idx / 16,
        MAX(exp_bits) - MIN(exp_bits), COUNT(exp_bits)
    FROM indexed
    GROUP BY alloc_type, alloc_addr, generation, idx / 16
    UNION ALL
    SELECT alloc_type, 32, alloc_addr, generation, idx / 32,
        MAX(exp_bits) - MIN(exp_bits), COUNT(exp_bits)
    FROM indexed
    GROUP BY alloc_type, alloc_addr, generation, idx / 32
    UNION ALL
    SELECT alloc_type, 64, alloc_addr, generation, idx / 64,
        MAX(exp_bits) - MIN(exp_bits), COUNT(exp_bits)
    FROM indexed
    GROUP BY alloc_type, alloc_addr, generation, idx / 64
    UNION ALL
    SELECT alloc_type, 128, alloc_addr, generation, idx / 128,
        MAX(exp_bits) - MIN(exp_bits), COUNT(exp_bits)
    FROM indexed
    GROUP BY alloc_type, alloc_addr, generation, idx / 128
)
SELECT
    '{bench}' AS bench,
    alloc_type, block_size,
    COUNT(*)::BIGINT                                          AS blocks,
    SUM(valid_n < 2 OR spread <= 4)::DOUBLE
        / NULLIF(COUNT(*), 0)                                 AS viable_spread4,
    SUM(valid_n < 2 OR spread <= 8)::DOUBLE
        / NULLIF(COUNT(*), 0)                                 AS viable_spread8,
    AVG(spread) FILTER (WHERE valid_n >= 2)                   AS mean_spread
FROM spreads
GROUP BY alloc_type, block_size
ORDER BY alloc_type, block_size;
