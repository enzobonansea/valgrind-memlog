-- Validation: correctness — IEEE-754 exponent-field histogram on captured
-- values. If the instrumentation corrupted writes (lost low bits, swapped
-- lanes on SIMD decomposition, wrote stale tree-node payload, etc.) the
-- exponent-field share of benchmarks whose 8-byte buffers are dominated by
-- IEEE-754 bit patterns would deviate sharply from the physically realistic
-- range. This query bins each captured uint64 by the binary64 exponent field
-- and reports per-(bench, alloc_type) shares — empirical evidence to back
-- the categorical "logged values match written values" claim that the unit
-- suite samples on 11 fixed bit-patterns.
--
-- Bit layout used (binary64): exp = (value >> 52) & 0x7FF.
--   exp == 0 and value == 0      -> exact zero (zero-init / scrubbed memory)
--   exp == 0 and value != 0      -> exponent field = 0 (IEEE subnormal class,
--                                   but also matches small-magnitude integers)
--   exp == 0x7FF                 -> exponent field saturated (IEEE inf/NaN class)
--   1 <= exp <= 0x7FE            -> exponent field in the IEEE normal range
--
-- These are exact bit-pattern shares — they make NO claim that any individual
-- value is a float. A capture bug would show up as a benchmark whose 64bits
-- shares (which we expect to track IEEE bit-pattern populations) suddenly
-- skew toward saturated exponents or random distributions. The 32bits row
-- mirrors this using the binary32 layout for cross-check.
WITH d AS (
    SELECT
        bench,
        alloc_type,
        value,
        ((value >> 52) & 2047) AS exp64,
        ((value >> 23) & 255)  AS exp32
    FROM all_stores
)
SELECT
    bench,
    alloc_type,
    COUNT(*)::BIGINT                                                 AS stores,
    SUM(value = 0)::DOUBLE / COUNT(*)                                AS frac_zero,
    -- 64-bit interpretation
    SUM(alloc_type = '64bits' AND value <> 0
        AND exp64 BETWEEN 1 AND 2046)::DOUBLE / NULLIF(COUNT(*), 0)  AS frac_normal_f64,
    SUM(alloc_type = '64bits' AND value <> 0 AND exp64 = 0)::DOUBLE
        / NULLIF(COUNT(*), 0)                                        AS frac_subnormal_f64,
    SUM(alloc_type = '64bits' AND exp64 = 2047)::DOUBLE
        / NULLIF(COUNT(*), 0)                                        AS frac_inf_nan_f64,
    -- 32-bit interpretation (low half of the 64-bit logged value)
    SUM(alloc_type = '32bits' AND (value & 0xFFFFFFFF) <> 0
        AND exp32 BETWEEN 1 AND 254)::DOUBLE / NULLIF(COUNT(*), 0)   AS frac_normal_f32,
    SUM(alloc_type = '32bits' AND (value & 0xFFFFFFFF) <> 0
        AND exp32 = 0)::DOUBLE / NULLIF(COUNT(*), 0)                 AS frac_subnormal_f32,
    SUM(alloc_type = '32bits' AND exp32 = 255)::DOUBLE
        / NULLIF(COUNT(*), 0)                                        AS frac_inf_nan_f32
FROM d
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
