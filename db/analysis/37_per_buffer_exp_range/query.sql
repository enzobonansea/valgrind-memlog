-- IEEE-754 exponent range per individual buffer (alloc_addr, generation).
-- Companion to 36_per_buffer_feasibility: mantissa trailing zeros answer
-- the precision half of "can this buffer live in a narrower format";
-- this query answers the range half. A buffer converts to a standard
-- format only if its observed unbiased-exponent window fits the format's:
--   FP8 E4M3 normals: [-6, 8]     FP8 E5M2: [-14, 15]
--   bfloat16 / FP32:  [-126, 127]
-- Zeros are representable everywhere and are excluded from the window;
-- denormal / Inf / NaN stores are counted separately (n_special) so a
-- buffer with special-value traffic can be flagged rather than silently
-- classified. Same extraction as 24_required_exp_bits, kept per buffer.
-- Per-bench iteration bounds the hash aggregate to one parquet's buffers.
WITH classified AS (
    SELECT
        alloc_addr, generation, alloc_type, alloc_size,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN '32bits' THEN ((value >> 23) & 255)::INT
        END AS biased,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT - 1023
            WHEN '32bits' THEN ((value >> 23) & 255)::INT  - 127
        END AS unbiased,
        (value = 0) AS is_zero
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
)
SELECT
    '{bench}'                                  AS bench,
    printf('0x%x', alloc_addr)                 AS addr,
    generation,
    alloc_type,
    alloc_size,
    COUNT(*)::BIGINT                           AS total,
    COUNT(*) FILTER (WHERE is_zero)::BIGINT    AS n_zero,
    COUNT(*) FILTER (
        WHERE NOT is_zero AND (
            biased = 0
            OR biased = CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
        ))::BIGINT                             AS n_special,
    MIN(unbiased) FILTER (
        WHERE NOT is_zero AND biased <> 0
          AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
    )                                          AS min_e,
    MAX(unbiased) FILTER (
        WHERE NOT is_zero AND biased <> 0
          AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
    )                                          AS max_e
FROM classified
GROUP BY alloc_addr, generation, alloc_type, alloc_size
ORDER BY total DESC;
