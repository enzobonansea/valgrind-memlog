-- Reduced-precision format feasibility per individual buffer
-- (alloc_addr, generation). Same trailing-zero thresholds as
-- 12_format_feasibility — a value is losslessly representable in a
-- target format when its mantissa has at least N trailing zeros:
--   32-bit values (23-bit mantissa): E4M3 >= 20, E5M2 >= 21, bf16 >= 16, FP16 >= 13.
--   64-bit values (52-bit mantissa): E4M3 >= 49, E5M2 >= 50, bf16 >= 45,
--                                    FP16 >= 42, FP32 >= 29.
-- Kept at buffer granularity to back the paper figure showing how
-- representability varies between buffers of the same benchmark.
-- Per-bench iteration bounds the hash-aggregate to one parquet's buffers.
--
-- Caveat (as Q12): alloc_type is alignment-derived, not "is float";
-- integer-heavy buffers show inflated representability.
WITH masked AS (
    SELECT
        alloc_addr, generation, alloc_type, alloc_size,
        CASE alloc_type
            WHEN '64bits' THEN value & ((1::UBIGINT << 52) - 1)
            WHEN '32bits' THEN value & ((1::UBIGINT << 23) - 1)
        END AS m
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
),
tz AS (
    SELECT
        alloc_addr, generation, alloc_type, alloc_size,
        CASE
            WHEN m = 0 AND alloc_type = '64bits' THEN 52
            WHEN m = 0 AND alloc_type = '32bits' THEN 23
            ELSE bit_count(xor(m::BIGINT, (m - 1)::BIGINT)) - 1
        END AS tz
    FROM masked
)
SELECT
    '{bench}'                                  AS bench,
    printf('0x%x', alloc_addr)                 AS addr,
    generation,
    alloc_type,
    alloc_size,
    COUNT(*)::BIGINT                                         AS total,
    SUM(tz >= CASE alloc_type WHEN '64bits' THEN 49 ELSE 20 END)::DOUBLE
        / COUNT(*)                                           AS pct_fp8_e4m3,
    SUM(tz >= CASE alloc_type WHEN '64bits' THEN 50 ELSE 21 END)::DOUBLE
        / COUNT(*)                                           AS pct_fp8_e5m2,
    SUM(tz >= CASE alloc_type WHEN '64bits' THEN 45 ELSE 16 END)::DOUBLE
        / COUNT(*)                                           AS pct_bf16,
    SUM(tz >= CASE alloc_type WHEN '64bits' THEN 42 ELSE 13 END)::DOUBLE
        / COUNT(*)                                           AS pct_fp16,
    CASE alloc_type
        WHEN '64bits' THEN SUM(tz >= 29)::DOUBLE / COUNT(*)
        ELSE 1.0
    END                                                      AS pct_fp32
FROM tz
GROUP BY alloc_addr, generation, alloc_type, alloc_size
ORDER BY total DESC;
