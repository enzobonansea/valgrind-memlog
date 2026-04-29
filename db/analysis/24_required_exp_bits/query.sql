-- Minimum exponent bit-width required per allocation site to cover the
-- observed dynamic range without overflow / underflow. Inspired by the
-- FPVM "tiny floats" paper (Hale et al., HPDC '26 ref/hpdc26-paper73.md):
-- the central empirical question of choosing a low-precision format for an
-- application is "what's the smallest exponent that won't truncate the
-- live values". This query answers it per source-level function.
--
-- For each site:
--   min_exp / max_exp : observed unbiased exponents (excluding zero,
--                       denormal, NaN, Inf)
--   exp_range         : max_exp - min_exp + 1 distinct unbiased exponents
--   required_e_bits   : ceil(log2(exp_range)) — the minimum number of
--                       exponent bits a custom IEEE-754-like format would
--                       need to span the full observed range. Compare
--                       against IEEE-754 widths: FP8 E4M3 = 4, FP8 E5M2 = 5,
--                       bf16 = 8, FP32 = 8, FP64 = 11.
--
-- A site whose required_e_bits ≤ 4 is a candidate for FP8 E4M3; ≤ 5 fits
-- E5M2; ≤ 8 fits bfloat16. Combine with 13_per_function_feasibility.sql
-- (which checks precision via mantissa) to identify functions that fit
-- both axes.
-- Per-bench iteration so the per-stack hash agg stays bounded by one
-- bench's stack dictionary.
WITH classified AS (
    SELECT
        alloc_stack,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN '32bits' THEN ((value >> 23) & 255)::INT
        END AS biased,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT - 1023
            WHEN '32bits' THEN ((value >> 23) & 255)::INT  - 127
        END AS unbiased,
        alloc_type
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits') AND value <> 0
),
per_stack AS (
    SELECT
        alloc_stack, alloc_type,
        MIN(unbiased) FILTER (
            WHERE biased <> 0
              AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
        ) AS min_e,
        MAX(unbiased) FILTER (
            WHERE biased <> 0
              AND biased <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
        ) AS max_e,
        COUNT(*)::BIGINT AS total
    FROM classified
    GROUP BY alloc_stack, alloc_type
),
sited AS (
    SELECT *,
        regexp_extract(
            COALESCE(
                list_filter(
                    string_split(alloc_stack, chr(10)),
                    line -> NOT regexp_matches(
                        lower(line),
                        'malloc|calloc|realloc|free|operator new|operator delete'
                        '|libgfortran|libstdc\+\+|ld-2\.|dl-init|\?\?\?')
                )[1],
                string_split(alloc_stack, chr(10))[2],
                string_split(alloc_stack, chr(10))[1],
                ''
            ),
            ': (.*?) \(', 1
        ) AS site
    FROM per_stack
),
agg AS (
    SELECT
        alloc_type, site,
        MIN(min_e)::INT AS min_e,
        MAX(max_e)::INT AS max_e,
        SUM(total)::BIGINT AS total
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
      AND min_e IS NOT NULL AND max_e IS NOT NULL
    GROUP BY alloc_type, site
    HAVING SUM(total) >= 1000
)
SELECT
    '{bench}' AS bench, alloc_type, site,
    min_e, max_e,
    max_e - min_e + 1                                          AS exp_range,
    CAST(CEIL(LOG2(GREATEST(max_e - min_e + 1, 2)::DOUBLE)) AS INT) AS required_e_bits,
    total
FROM (
    SELECT *,
        ROW_NUMBER() OVER (ORDER BY total DESC) AS rnk
    FROM agg
)
WHERE rnk <= 20
ORDER BY total DESC;
