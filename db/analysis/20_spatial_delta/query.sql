-- @set threads 2
-- @set watch_spill_gb 130
-- Spatial value similarity between physically-adjacent offsets in the
-- last-write snapshot of each buffer. Complements 09 and 10 (which measure
-- *temporal* similarity — same-offset, consecutive stores) by measuring
-- *spatial* similarity — adjacent-offset, same-snapshot. Spatial similarity
-- is what delta-encoded compressors (BDI, FPC) and structured-grid
-- numerical kernels actually exploit.
--
-- Per (bench, alloc_type):
--   bit_identical  : pairs where the two adjacent offsets store the exact
--                    same value
--   delta_le_8b    : pairs whose Hamming distance is ≤ 8 bits — i.e. an
--                    8-bit XOR-delta would suffice
--   delta_le_16b   : same, ≤ 16 bits
--   mean_hamming   : average Hamming distance per adjacent pair
--   mean_log_delta : average ceil(log2(|val - prev_val|+1)) — a rough proxy
--                    for the bit-width of the additive delta. Useful for
--                    delta encoders that work in arithmetic difference
--                    rather than bitwise XOR.
-- Per-bench iteration bounds window state to one parquet at a time.
-- Snapshot extraction uses arg_max(value, rn) (rn = parquet file_row_number
-- from the view) instead of the earlier ROW_NUMBER OVER () + QUALIFY
-- pattern, whose global window forced a spill-heavy materialise.
WITH snapshot AS (
    SELECT alloc_type, alloc_addr, generation, "offset",
        arg_max(value, rn) AS value
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
    GROUP BY alloc_type, alloc_addr, generation, "offset"
),
adj AS (
    SELECT alloc_type, value,
        LAG(value) OVER (
            PARTITION BY alloc_addr, generation
            ORDER BY "offset") AS prev_value,
        CASE alloc_type
            WHEN '32bits' THEN (1::UBIGINT << 32) - 1
            ELSE 18446744073709551615::UBIGINT
        END AS mask
    FROM snapshot
)
SELECT
    '{bench}' AS bench,
    alloc_type,
    COUNT(*) FILTER (WHERE prev_value IS NOT NULL)::BIGINT      AS pairs,
    SUM(prev_value = value) FILTER (WHERE prev_value IS NOT NULL)::BIGINT
                                                                AS bit_identical,
    SUM(bit_count(xor(value, prev_value) & mask) <= 8)
        FILTER (WHERE prev_value IS NOT NULL)::BIGINT           AS delta_le_8b,
    SUM(bit_count(xor(value, prev_value) & mask) <= 16)
        FILTER (WHERE prev_value IS NOT NULL)::BIGINT           AS delta_le_16b,
    AVG(bit_count(xor(value, prev_value) & mask))
        FILTER (WHERE prev_value IS NOT NULL)                   AS mean_hamming,
    AVG(
        CASE
            WHEN value = prev_value THEN 0
            ELSE CEIL(LOG2((CASE WHEN value > prev_value
                                 THEN value - prev_value
                                 ELSE prev_value - value END) + 1))
        END
    ) FILTER (WHERE prev_value IS NOT NULL)                     AS mean_log_delta
FROM adj
GROUP BY alloc_type
ORDER BY alloc_type;
