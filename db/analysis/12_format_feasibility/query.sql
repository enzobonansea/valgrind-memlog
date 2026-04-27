-- Reduced-precision format feasibility per (bench, alloc_type).
-- A value is "losslessly representable" in a target format when its IEEE-754
-- mantissa has at least N trailing zero bits, where N is the number of
-- mantissa bits dropped by the target format:
--   for 32-bit values (mantissa = 23 bits):   FP8 E4M3 >= 20, FP8 E5M2 >= 21,
--                                             bf16 >= 16, FP16 >= 13.
--   for 64-bit values (mantissa = 52 bits):   FP8 E4M3 >= 49, FP8 E5M2 >= 50,
--                                             bf16 >= 45, FP16 >= 42, FP32 >= 29.
-- Trailing-zero count via bit_count(xor(m, m-1)) - 1 (popcount of the run of
-- ones up through the lowest set bit, minus one).
--
-- Caveat: alloc_type is alignment-derived, not "is float" — the heuristic is
-- applied uniformly. Integer-heavy buffers will show inflated representability
-- (small integers have many trailing zeros in their mantissa-window).
WITH masked AS (
    SELECT
        bench,
        alloc_type,
        CASE alloc_type
            WHEN '64bits' THEN value & ((1::UBIGINT << 52) - 1)
            WHEN '32bits' THEN value & ((1::UBIGINT << 23) - 1)
        END AS m
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits')
),
tz AS (
    SELECT
        bench,
        alloc_type,
        CASE
            WHEN m = 0 AND alloc_type = '64bits' THEN 52
            WHEN m = 0 AND alloc_type = '32bits' THEN 23
            ELSE bit_count(xor(m::BIGINT, (m - 1)::BIGINT)) - 1
        END AS tz
    FROM masked
)
SELECT
    bench,
    alloc_type,
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
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
