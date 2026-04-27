-- Per-allocation-site reduced-precision feasibility (matches paper Table 4).
-- Same trailing-zero thresholds as 12_format_feasibility.sql, but grouped by
-- the first non-allocator stack frame so the per-function divergence shows up
-- (e.g. WRF's solve_em_ vs surface_driver).
--
-- Skip-list:
-- malloc, calloc, realloc, free, operator new/delete, libgfortran, libstdc++,
-- ld-2., dl-init, ???.
--
-- Performance: aggregate trailing-zero counts per (bench, alloc_type,
-- alloc_stack) in a single scan (DuckDB groups on the dictionary index of
-- alloc_stack so this is ~free), then extract the site name from each
-- unique stack once and re-aggregate by site.
--
-- NOT memory-bound — CPU-bound (per-row bit_count/xor + regex_extract
-- over billions of stores). Benefits from more threads; doesn't need the
-- low-memory_limit/low-thread regime that the window-heavy queries need.
WITH per_stack AS (
    SELECT
        bench, alloc_type, alloc_stack,
        COUNT(*)::BIGINT AS total,
        SUM(tz >= CASE alloc_type WHEN '64bits' THEN 49 ELSE 20 END)::BIGINT AS n_fp8_e4m3,
        SUM(tz >= CASE alloc_type WHEN '64bits' THEN 50 ELSE 21 END)::BIGINT AS n_fp8_e5m2,
        SUM(tz >= CASE alloc_type WHEN '64bits' THEN 45 ELSE 16 END)::BIGINT AS n_bf16,
        SUM(tz >= CASE alloc_type WHEN '64bits' THEN 42 ELSE 13 END)::BIGINT AS n_fp16,
        SUM(CASE WHEN alloc_type = '64bits' AND tz >= 29 THEN 1 ELSE 0 END)::BIGINT AS n_fp32
    FROM (
        SELECT bench, alloc_type, alloc_stack,
            CASE
                WHEN m = 0 AND alloc_type = '64bits' THEN 52
                WHEN m = 0 AND alloc_type = '32bits' THEN 23
                ELSE bit_count(xor(m::BIGINT, (m - 1)::BIGINT)) - 1
            END AS tz
        FROM (
            SELECT bench, alloc_type, alloc_stack,
                CASE alloc_type
                    WHEN '64bits' THEN value & ((1::UBIGINT << 52) - 1)
                    WHEN '32bits' THEN value & ((1::UBIGINT << 23) - 1)
                END AS m
            FROM all_stores
            WHERE alloc_type IN ('32bits', '64bits')
        )
    )
    GROUP BY bench, alloc_type, alloc_stack
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
        bench, alloc_type, site,
        SUM(total)::BIGINT                                      AS total,
        SUM(n_fp8_e4m3)::DOUBLE / NULLIF(SUM(total), 0)         AS pct_fp8_e4m3,
        SUM(n_fp8_e5m2)::DOUBLE / NULLIF(SUM(total), 0)         AS pct_fp8_e5m2,
        SUM(n_bf16)::DOUBLE     / NULLIF(SUM(total), 0)         AS pct_bf16,
        SUM(n_fp16)::DOUBLE     / NULLIF(SUM(total), 0)         AS pct_fp16,
        CASE alloc_type
            WHEN '64bits' THEN SUM(n_fp32)::DOUBLE / NULLIF(SUM(total), 0)
            ELSE NULL
        END                                                     AS pct_fp32
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
    GROUP BY bench, alloc_type, site
    HAVING SUM(total) >= 1000
)
SELECT bench, alloc_type, site, total,
       pct_fp8_e4m3, pct_fp8_e5m2, pct_bf16, pct_fp16, pct_fp32
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY bench ORDER BY total DESC) AS rnk
    FROM agg
)
WHERE rnk <= 20
ORDER BY bench, total DESC;
