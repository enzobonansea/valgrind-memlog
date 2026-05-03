-- @set threads 2
-- Per-allocation-site write profiling (paper figs alloc_site_profile_*).
-- For each benchmark, ranks the allocation sites (extracted from the first
-- non-allocator stack frame) by total stores. Reveals whether write traffic
-- concentrates in a single hot function (e.g. WRF's solve_em_ ≈ 85%) or
-- spreads across many sites.
--
-- Skip-list and site-extraction logic match 13_per_function_feasibility.sql.
-- Trailing-zero column gives a quick precision proxy without the full
-- format-feasibility breakdown.
--
-- Per-bench iteration so the per-stack hash agg stays bounded by one
-- bench's stack dictionary (and so COUNT(DISTINCT (alloc_addr, generation))
-- is replaced by a two-stage GROUP BY: collapse to one row per buffer
-- first, then count rows per site).
WITH per_buffer AS (
    SELECT alloc_stack, alloc_addr, generation,
        any_value(alloc_size) AS alloc_size,
        COUNT(*)::BIGINT      AS stores,
        SUM(CASE
                WHEN alloc_type NOT IN ('32bits', '64bits') THEN NULL
                WHEN m = 0 AND alloc_type = '64bits' THEN 52
                WHEN m = 0 AND alloc_type = '32bits' THEN 23
                ELSE bit_count(xor(m::BIGINT, (m - 1)::BIGINT)) - 1
            END)::DOUBLE      AS sum_trailing_z,
        SUM(CASE WHEN alloc_type IN ('32bits', '64bits') THEN 1 ELSE 0 END)::BIGINT
                              AS num_trailing_z
    FROM (
        SELECT alloc_stack, alloc_addr, generation,
               alloc_type, alloc_size,
               CASE alloc_type
                   WHEN '64bits' THEN value & ((1::UBIGINT << 52) - 1)
                   WHEN '32bits' THEN value & ((1::UBIGINT << 23) - 1)
                   ELSE NULL
               END AS m
        FROM {bench}
    )
    GROUP BY alloc_stack, alloc_addr, generation
),
per_stack AS (
    SELECT alloc_stack,
        SUM(stores)::BIGINT                                    AS stores,
        COUNT(*)::BIGINT                                       AS buffers,
        SUM(stores * alloc_size)::DOUBLE / NULLIF(SUM(stores), 0)
                                                               AS mean_alloc_size,
        SUM(sum_trailing_z) / NULLIF(SUM(num_trailing_z), 0)   AS mean_trailing_z
    FROM per_buffer
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
    SELECT site,
        SUM(stores)::BIGINT                              AS stores,
        SUM(buffers)::BIGINT                             AS buffers,
        SUM(stores * mean_alloc_size) / SUM(stores)      AS mean_alloc_size,
        SUM(stores * COALESCE(mean_trailing_z, 0))
            / NULLIF(SUM(stores), 0)                     AS mean_trailing_z
    FROM sited
    WHERE site IS NOT NULL AND site <> ''
    GROUP BY site
)
SELECT '{bench}' AS bench, site, stores,
       100.0 * stores / SUM(stores) OVER ()               AS pct_of_bench,
       buffers,
       mean_alloc_size,
       mean_trailing_z
FROM agg
ORDER BY stores DESC
LIMIT 15;
