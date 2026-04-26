-- Per-allocation-site write profiling (paper figs alloc_site_profile_*).
-- For each benchmark, ranks the allocation sites (extracted from the first
-- non-allocator stack frame) by total stores. Reveals whether write traffic
-- concentrates in a single hot function (e.g. WRF's solve_em_ ≈ 85%) or
-- spreads across many sites.
--
-- Skip-list and site-extraction logic match 13_per_function_feasibility.sql.
-- Trailing-zero column gives a quick precision proxy without the full
-- format-feasibility breakdown.
WITH per_stack AS (
    SELECT
        bench, alloc_stack,
        COUNT(*)::BIGINT                                            AS stores,
        COUNT(DISTINCT (alloc_addr, generation))::BIGINT            AS buffers,
        AVG(alloc_size)                                             AS mean_alloc_size,
        AVG(
            CASE
                WHEN alloc_type NOT IN ('32bits', '64bits') THEN NULL
                WHEN m = 0 AND alloc_type = '64bits' THEN 52
                WHEN m = 0 AND alloc_type = '32bits' THEN 23
                ELSE bit_count(xor(m::BIGINT, (m - 1)::BIGINT)) - 1
            END
        )                                                           AS mean_trailing_z
    FROM (
        SELECT bench, alloc_stack, alloc_addr, generation,
               alloc_type, alloc_size,
               CASE alloc_type
                   WHEN '64bits' THEN value & ((1::UBIGINT << 52) - 1)
                   WHEN '32bits' THEN value & ((1::UBIGINT << 23) - 1)
                   ELSE NULL
               END AS m
        FROM all_stores
    )
    GROUP BY bench, alloc_stack
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
    SELECT bench, site,
        SUM(stores)::BIGINT                              AS stores,
        SUM(buffers)::BIGINT                             AS buffers,
        SUM(stores * mean_alloc_size) / SUM(stores)      AS mean_alloc_size,
        SUM(stores * COALESCE(mean_trailing_z, 0))
            / NULLIF(SUM(stores), 0)                     AS mean_trailing_z
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
    GROUP BY bench, site
)
SELECT bench, site, stores,
       100.0 * stores / SUM(stores) OVER (PARTITION BY bench)  AS pct_of_bench,
       buffers,
       mean_alloc_size,
       mean_trailing_z
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY bench ORDER BY stores DESC) AS rnk
    FROM agg
)
WHERE rnk <= 15
ORDER BY bench, stores DESC;
