-- Per-function silent-store rate (paper Table 2 headline: "CAM4's 4.8%
-- aggregate hides 49.8% in dyn_run"). Same definition as 09_silent_stores
-- — write that puts back the value already at (alloc_addr, generation,
-- offset) — but grouped by the first non-allocator stack frame.
--
-- Per-bench iteration bounds the window state to one parquet at a time.
-- Per-row LAG is computed once for this bench, then aggregated by
-- alloc_stack, then by alloc-site (so the regex runs once per unique
-- stack rather than per store).  ORDER BY uses the view's `rn` column
-- (parquet file_row_number) instead of an upstream ROW_NUMBER() OVER ()
-- whose global materialise blew DuckDB's spill budget.
WITH lagged AS (
    SELECT
        alloc_stack, value,
        LAG(value) OVER (
            PARTITION BY alloc_addr, generation, "offset"
            ORDER BY rn) AS prev_value
    FROM {bench}
),
per_stack AS (
    SELECT
        alloc_stack,
        COUNT(*)::BIGINT                                              AS stores,
        COUNT(*) FILTER (WHERE prev_value IS NOT NULL)::BIGINT        AS pairs,
        COUNT(*) FILTER (WHERE prev_value = value)::BIGINT            AS silent
    FROM lagged
    GROUP BY alloc_stack
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
        site,
        SUM(stores)::BIGINT                                AS stores,
        SUM(pairs)::BIGINT                                 AS pairs,
        SUM(silent)::BIGINT                                AS silent,
        SUM(silent)::DOUBLE / NULLIF(SUM(pairs), 0)        AS silent_frac
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
    GROUP BY site
    HAVING SUM(pairs) >= 1000
)
SELECT '{bench}' AS bench, site, stores, pairs, silent, silent_frac
FROM (
    SELECT *,
        ROW_NUMBER() OVER (ORDER BY pairs DESC) AS rnk
    FROM agg
)
WHERE rnk <= 20
ORDER BY pairs DESC;
