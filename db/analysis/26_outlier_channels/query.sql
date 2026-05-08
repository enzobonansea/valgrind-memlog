-- @set threads 4
-- @set memory_limit 16GB
-- @set watch_spill_gb 100
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
--   p999               IEEE-754-magnitude threshold (sign bit masked off
--                      so the unsigned value comparison ranks magnitudes)
--   n_outlier_999      stores above that magnitude
--   distinct_offsets   distinct offsets touched by the site (HLL estimate)
--   outlier_offsets    distinct offsets that ever carry a 99.9% outlier (HLL)
--   channel_frac       outlier_offsets / distinct_offsets
--                      small ⇒ outliers concentrate ⇒ per-channel scaling wins
--
-- Citations: Xiao 2023 ICML (SmoothQuant); Lin 2024 MLSys (AWQ);
-- Dettmers 2022 NeurIPS (LLM.int8()); Tseng 2024 NeurIPS (QuIP#).
--
-- Per-bench iteration so per-stack hash agg is bounded by one bench's
-- stack dictionary. Quantiles use APPROX_QUANTILE (t-digest, bounded
-- state) instead of QUANTILE_CONT (which materialises full per-group
-- value lists).
--
-- distinct_offsets and outlier_offsets are HLL estimates rather than
-- exact counts. The earlier exact rewrite materialised a per-(stack,
-- offset) pre-aggregate, which spilled >200 GB on cam4: stack count
-- is small (~1.6k) but a single Fortran array allocation can touch
-- millions of distinct offsets, so (stack × offset) cardinality runs
-- into the billions. With the 200 GB spill cap, exact counting is
-- infeasible for cam4-class benches; HLL collapses per-stack state to
-- ~16 KB regardless of offset cardinality. Two parquet scans (one for
-- the threshold, one for the per-stack agg) avoid materialising an
-- abs_vals CTE, which the optimiser otherwise spilled at one row per
-- store on the bigger benches.
WITH thresh AS (
    SELECT alloc_stack, alloc_type,
        APPROX_QUANTILE(
            CASE alloc_type
                WHEN '32bits' THEN value & ((1::UBIGINT << 31) - 1)
                WHEN '64bits' THEN value & ((1::UBIGINT << 63) - 1)
            END, 0.999) AS p999
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits') AND value <> 0
    GROUP BY alloc_stack, alloc_type
),
per_stack AS (
    SELECT b.alloc_stack, b.alloc_type,
        COUNT(*)::BIGINT AS total,
        SUM((
            (CASE b.alloc_type
                WHEN '32bits' THEN b.value & ((1::UBIGINT << 31) - 1)
                WHEN '64bits' THEN b.value & ((1::UBIGINT << 63) - 1)
            END) >= t.p999)::INT
        )::BIGINT AS n_outlier_999,
        APPROX_COUNT_DISTINCT(b."offset")::BIGINT AS distinct_offsets,
        APPROX_COUNT_DISTINCT(
            CASE WHEN
                (CASE b.alloc_type
                    WHEN '32bits' THEN b.value & ((1::UBIGINT << 31) - 1)
                    WHEN '64bits' THEN b.value & ((1::UBIGINT << 63) - 1)
                END) >= t.p999
            THEN b."offset" END
        )::BIGINT AS outlier_offsets
    FROM {bench} b
    JOIN thresh t USING (alloc_stack, alloc_type)
    WHERE b.alloc_type IN ('32bits', '64bits') AND b.value <> 0
    GROUP BY b.alloc_stack, b.alloc_type
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
        SUM(total)::BIGINT             AS total,
        SUM(n_outlier_999)::BIGINT     AS n_outlier_999,
        SUM(distinct_offsets)::BIGINT  AS distinct_offsets,
        SUM(outlier_offsets)::BIGINT   AS outlier_offsets,
        SUM(outlier_offsets)::DOUBLE
            / NULLIF(SUM(distinct_offsets), 0) AS channel_frac
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
    GROUP BY alloc_type, site
    HAVING SUM(total) >= 1000
)
SELECT '{bench}' AS bench, alloc_type, site, total,
       n_outlier_999, distinct_offsets, outlier_offsets, channel_frac
FROM (
    SELECT *, ROW_NUMBER() OVER (ORDER BY total DESC) AS rnk
    FROM agg
)
WHERE rnk <= 20
ORDER BY total DESC;
