-- Per-offset exponent stability across stores (decides per-tensor vs.
-- per-channel vs. per-token scaling for FP8 / MXFP4). For each
-- (alloc_site, offset) we look at the IEEE-754 exponent of every store
-- that ever lands there and report how tight that distribution is. If
-- exponents are constant per offset across the whole run, per-channel
-- scaling is exact; if they wander widely, only per-token scaling
-- (recompute scale every store) recovers full precision.
--
-- For each (bench, alloc_site, alloc_type):
--   distinct_offsets             # of offsets that received >= 2 stores
--   frac_constant_exp            fraction of those offsets whose unbiased
--                                exponent never changed (best case for
--                                per-channel scaling)
--   mean_exp_range               mean (max-min) per offset
--   median_exp_range             paper-friendly summary number
--   p95_exp_range                tail — worst 5% of offsets
--
-- Citations: Rouhani 2023 (Microscaling Data Formats); OCP MX spec 2023;
-- Dettmers 2023 NeurIPS (NF4 / per-block scale); Darvish-Rouhani 2020
-- NeurIPS (HFP8).
--
-- Per-bench iteration so the per-(stack, addr, gen, offset) hash agg —
-- the highest-cardinality grouping in the suite — stays bounded by one
-- bench at a time. Quantiles use APPROX_QUANTILE (t-digest, bounded
-- state) instead of QUANTILE_CONT.
WITH ex AS (
    SELECT alloc_stack, alloc_type, alloc_addr, generation, "offset",
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT - 1023
            WHEN '32bits' THEN ((value >> 23) & 255)::INT  - 127
        END AS unbiased_exp,
        CASE alloc_type
            WHEN '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN '32bits' THEN ((value >> 23) & 255)::INT
        END AS biased_exp
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits') AND value <> 0
),
per_offset AS (
    SELECT alloc_stack, alloc_type, alloc_addr, generation, "offset",
        MAX(unbiased_exp) - MIN(unbiased_exp) AS exp_range,
        COUNT(*) AS n
    FROM ex
    WHERE biased_exp <> 0
      AND biased_exp <> CASE alloc_type WHEN '64bits' THEN 2047 ELSE 255 END
    GROUP BY alloc_stack, alloc_type, alloc_addr, generation, "offset"
    HAVING COUNT(*) >= 2
),
per_stack AS (
    SELECT alloc_stack, alloc_type,
        COUNT(*)::BIGINT                                      AS distinct_offsets,
        SUM(exp_range = 0)::DOUBLE / COUNT(*)                 AS frac_constant_exp,
        AVG(exp_range)                                        AS mean_exp_range,
        APPROX_QUANTILE(exp_range, 0.5)                       AS median_exp_range,
        APPROX_QUANTILE(exp_range, 0.95)                      AS p95_exp_range
    FROM per_offset
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
    SELECT alloc_type, site,
        SUM(distinct_offsets)::BIGINT                                  AS distinct_offsets,
        SUM(distinct_offsets * frac_constant_exp) / SUM(distinct_offsets) AS frac_constant_exp,
        SUM(distinct_offsets * mean_exp_range)    / SUM(distinct_offsets) AS mean_exp_range,
        AVG(median_exp_range)                                           AS median_exp_range,
        MAX(p95_exp_range)                                              AS p95_exp_range
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
    GROUP BY alloc_type, site
    HAVING SUM(distinct_offsets) >= 100
)
SELECT '{bench}' AS bench, alloc_type, site, distinct_offsets,
       frac_constant_exp, mean_exp_range, median_exp_range, p95_exp_range
FROM (
    SELECT *,
        ROW_NUMBER() OVER (ORDER BY distinct_offsets DESC) AS rnk
    FROM agg
)
WHERE rnk <= 20
ORDER BY distinct_offsets DESC;
