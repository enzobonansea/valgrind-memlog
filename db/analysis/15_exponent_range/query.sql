-- IEEE-754 exponent stats per (bench, alloc_type).
-- Complements 12_format_feasibility.sql (which checks precision via mantissa
-- trailing zeros) by checking *range* — orthogonal axis of FP8 feasibility.
-- A value can fit in FP8 only if both its precision and its magnitude do.
--
-- FP8 E4M3 dynamic range : ~1e-9 .. 448  (unbiased exp in [-9, 8])
-- FP8 E5M2 dynamic range : ~1e-16 .. 57344 (unbiased exp in [-16, 15])
-- bfloat16 / FP16 share FP32's range
WITH classified AS (
    SELECT
        bench, alloc_type, value,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN '32bits' THEN ((value >> 23) & 255)::INT
        END                                                     AS biased,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT - 1023
            WHEN '32bits' THEN ((value >> 23) & 255)::INT  - 127
        END                                                     AS unbiased
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits')
)
SELECT
    bench, alloc_type,
    COUNT(*)::BIGINT                                            AS total,
    SUM(value = 0)::DOUBLE / COUNT(*)                           AS frac_zero,
    SUM(value <> 0 AND biased = 0)::DOUBLE / COUNT(*)           AS frac_denormal,
    SUM(biased = CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END)::DOUBLE
        / COUNT(*)                                              AS frac_inf_nan,
    -- "normal" finite, non-zero: 0 < biased < max
    MIN(unbiased) FILTER (
        WHERE biased <> 0
          AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
    )                                                           AS min_exp,
    MAX(unbiased) FILTER (
        WHERE biased <> 0
          AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
    )                                                           AS max_exp,
    AVG(unbiased) FILTER (
        WHERE biased <> 0
          AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
    )                                                           AS mean_exp,
    SUM(unbiased BETWEEN -9 AND 8)::DOUBLE  / COUNT(*)          AS frac_in_e4m3_range,
    SUM(unbiased BETWEEN -16 AND 15)::DOUBLE / COUNT(*)         AS frac_in_e5m2_range
FROM classified
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
