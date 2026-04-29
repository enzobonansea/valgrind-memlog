-- Bit-pattern statistics per benchmark / alloc_type.
--   zero_values    : value is exactly 0
--   exp_zero       : IEEE-754 biased exponent is 0 (the value is zero or a
--                    subnormal when reinterpreted as float)
--   mantissa_zero  : mantissa bits are all 0 (exact power of two, or zero)
--   bit_identical  : consecutive stores within the same (alloc_addr, generation)
--                    that write the same value as the previous store —
--                    i.e. spatial coherence, NOT silent stores (silent stores
--                    require the same offset; see 09_silent_stores.sql).
--   mean_hamming   : average Hamming distance between value and the previous
--                    store in the same alloc, masked to 32 or 64 bits.
--
-- Useful for spotting:
--   * sparse / zero-padded buffers          → high zero_values, exp_zero
--   * spatially coherent numeric arrays      → high bit_identical, low mean_hamming
--
-- Per-bench iteration bounds the window state to one parquet at a time.
-- Ordering note: same convention as 09_silent_stores — the view's `rn`
-- column is parquet's file_row_number, so ORDER BY rn within
-- (alloc_addr, generation) reproduces the temporal store sequence without
-- the global ROW_NUMBER() OVER () materialise that earlier revisions used.
WITH neighbored AS (
    SELECT
        alloc_type, value,
        LAG(value) OVER (
            PARTITION BY alloc_addr, generation
            ORDER BY rn
        ) AS prev_value
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
)
SELECT
    '{bench}' AS bench,
    alloc_type,
    COUNT(*)::BIGINT                                                       AS total,
    SUM(value = 0)::BIGINT                                                 AS zero_values,
    SUM(CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047) = 0
            WHEN '32bits' THEN ((value >> 23) & 255)  = 0
        END)::BIGINT                                                       AS exp_zero,
    SUM(CASE alloc_type
            WHEN '64bits' THEN (value & ((1::UBIGINT << 52) - 1)) = 0
            WHEN '32bits' THEN (value & ((1::UBIGINT << 23) - 1)) = 0
        END)::BIGINT                                                       AS mantissa_zero,
    COUNT(*)            FILTER (WHERE prev_value IS NOT NULL)::BIGINT      AS pairs,
    SUM(prev_value = value) FILTER (WHERE prev_value IS NOT NULL)::BIGINT  AS bit_identical,
    AVG(
        bit_count(
            xor(value, prev_value) &
            CASE alloc_type
                WHEN '32bits' THEN (1::UBIGINT << 32) - 1
                ELSE          18446744073709551615::UBIGINT  -- (1<<64)-1
            END
        )
    ) FILTER (WHERE prev_value IS NOT NULL)                                AS mean_hamming
FROM neighbored
GROUP BY alloc_type
ORDER BY alloc_type;
