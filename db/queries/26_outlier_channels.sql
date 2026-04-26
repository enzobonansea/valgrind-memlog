-- Outlier-channel concentration per allocation site (SmoothQuant / AWQ /
-- QuIP-style analysis). LLM-quantization papers show that quantization
-- error is dominated by a small set of outlier "channels" — fixed
-- positions in a tensor that consistently hold large-magnitude values.
-- The offset axis in Memlog *is* the channel axis at runtime, so this
-- query measures whether outliers concentrate at a few stable offsets
-- per allocation site (yes ⇒ per-channel scaling viable) or spread
-- everywhere (no ⇒ per-tensor scaling forced).
--
-- For each (bench, alloc_site, alloc_type):
--   p99 / p999          IEEE-754-magnitude thresholds (sign bit masked off
--                       so the unsigned value comparison ranks magnitudes)
--   n_outlier_99/.999   stores above that magnitude
--   distinct_offsets    distinct offsets touched by the site
--   outlier_offsets     distinct offsets that ever carry a 99.9% outlier
--   channel_frac        outlier_offsets / distinct_offsets
--                       small ⇒ outliers concentrate ⇒ per-channel scaling wins
--
-- Citations: Xiao 2023 ICML (SmoothQuant); Lin 2024 MLSys (AWQ);
-- Dettmers 2022 NeurIPS (LLM.int8()); Tseng 2024 NeurIPS (QuIP#).
WITH abs_vals AS (
    SELECT
        bench, alloc_stack, alloc_type, "offset",
        CASE alloc_type
            WHEN '32bits' THEN value & ((1::UBIGINT << 31) - 1)
            WHEN '64bits' THEN value & ((1::UBIGINT << 63) - 1)
        END AS abs_bits
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits') AND value <> 0
),
thresh AS (
    SELECT bench, alloc_stack, alloc_type,
        APPROX_QUANTILE(abs_bits, 0.99)  AS p99,
        APPROX_QUANTILE(abs_bits, 0.999) AS p999
    FROM abs_vals
    GROUP BY bench, alloc_stack, alloc_type
),
flagged AS (
    SELECT av.bench, av.alloc_stack, av.alloc_type, av."offset",
        (av.abs_bits >= t.p99)  AS o99,
        (av.abs_bits >= t.p999) AS o999
    FROM abs_vals av
    JOIN thresh t USING (bench, alloc_stack, alloc_type)
),
per_stack AS (
    SELECT bench, alloc_stack, alloc_type,
        COUNT(*)::BIGINT                                        AS total,
        SUM(o99::INT)::BIGINT                                   AS n_outlier_99,
        SUM(o999::INT)::BIGINT                                  AS n_outlier_999,
        COUNT(DISTINCT "offset")::BIGINT                        AS distinct_offsets,
        COUNT(DISTINCT CASE WHEN o999 THEN "offset" END)::BIGINT AS outlier_offsets
    FROM flagged
    GROUP BY bench, alloc_stack, alloc_type
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
    SELECT bench, alloc_type, site,
        SUM(total)::BIGINT             AS total,
        SUM(n_outlier_999)::BIGINT     AS n_outlier_999,
        SUM(distinct_offsets)::BIGINT  AS distinct_offsets,
        SUM(outlier_offsets)::BIGINT   AS outlier_offsets,
        SUM(outlier_offsets)::DOUBLE
            / NULLIF(SUM(distinct_offsets), 0) AS channel_frac
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
    GROUP BY bench, alloc_type, site
    HAVING SUM(total) >= 1000
)
SELECT bench, alloc_type, site, total,
       n_outlier_999, distinct_offsets, outlier_offsets, channel_frac
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY bench ORDER BY total DESC) AS rnk
    FROM agg
)
WHERE rnk <= 20
ORDER BY bench, total DESC;
