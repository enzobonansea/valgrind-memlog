-- Posit-suitability profile per (bench, alloc_type). Posit numbers
-- [Gustafson 2017] dedicate variable mantissa width based on magnitude:
-- values near 1.0 get more precision than IEEE-754 floats, values near
-- the extremes get less. The metric is whether a workload's value
-- distribution lives in the precision sweet spot or wanders to magnitudes
-- where posits give few mantissa bits.
--
-- For posit-32 (es=2):
--   |unbiased_exp| <= 4   ⇒ ≥ 28 mantissa bits  (vs IEEE-32's 23)
--   |unbiased_exp| <= 16  ⇒ ≥ 22 mantissa bits  (still competitive)
--   |unbiased_exp| >  30  ⇒  < 14 mantissa bits  (worse than IEEE)
--
-- Per (bench, alloc_type):
--   mean_abs_exp                average |unbiased_exp| of finite, non-zero
--                               stores
--   frac_high_precision         |exp| <= 4   — posit-32 wins big here
--   frac_mid_precision          |exp| <= 16  — posit-32 still wins
--   frac_extreme                |exp| >  30  — IEEE wins
--   mean_posit_useful_bits      crude weighted score: max(0, 28 - |exp|/2)
--                               averaged over all stores. Higher = posits
--                               give more usable mantissa bits than IEEE.
--
-- Citations: Gustafson 2017 SuperFri (Posit Arithmetic); Cococcioni 2022
-- IEEE Computer (posits for DNN); Klöwer 2020 Nature CompSci (posits in
-- climate); Posit Standard 2022.
WITH classified AS (
    SELECT bench, alloc_type,
        ABS(
            CASE alloc_type
                WHEN '64bits' THEN ((value >> 52) & 2047)::INT - 1023
                WHEN '32bits' THEN ((value >> 23) & 255)::INT  - 127
            END
        ) AS abs_exp,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN '32bits' THEN ((value >> 23) & 255)::INT
        END AS biased
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits') AND value <> 0
)
SELECT
    bench, alloc_type,
    COUNT(*)::BIGINT                                            AS total,
    AVG(abs_exp::DOUBLE) FILTER (
        WHERE biased <> 0
          AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
    )                                                            AS mean_abs_exp,
    SUM(abs_exp <=  4)::DOUBLE / COUNT(*)                        AS frac_high_precision,
    SUM(abs_exp <= 16)::DOUBLE / COUNT(*)                        AS frac_mid_precision,
    SUM(abs_exp >  30)::DOUBLE / COUNT(*)                        AS frac_extreme,
    AVG(GREATEST(0, 28.0 - abs_exp / 2.0))                       AS mean_posit_useful_bits
FROM classified
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
