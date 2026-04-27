-- Validation: correctness — IEEE-754 sanity check on captured 64-bit values.
-- If the instrumentation corrupted writes (lost low bits, swapped lanes on
-- SIMD decomposition, wrote stale tree-node payload, etc.) the unbiased
-- exponent distribution of FP-heavy benchmarks would deviate sharply from
-- physically realistic ranges. This query bins captured uint64 reinterpretations
-- into the four IEEE-754 binary64 classes and reports per-(bench, alloc_type)
-- shares — providing empirical, at-scale evidence to back the categorical
-- "logged values match written values" claim that the unit suite samples on
-- 11 fixed bit-patterns.
--
-- Bit layout used (binary64): exp = (value >> 52) & 0x7FF.
--   exp == 0 and value == 0      -> exact zero (zero-init / scrubbed memory)
--   exp == 0 and value != 0      -> subnormal (or non-FP small int payload)
--   exp == 0x7FF                 -> inf / NaN
--   1 <= exp <= 0x7FE            -> normal — the realistic bulk for FP code
--
-- Pathological signature: a benchmark with predominantly normal FP behavior
-- showing an unexpectedly large 'inf_nan' or random exponent share would
-- indicate a capture bug. The 32bits classification mirrors the 64bits one
-- using the binary32 layout for cross-check.
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
