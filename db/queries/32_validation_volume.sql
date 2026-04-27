-- Validation: per-benchmark testing volume. Establishes the *scale* at which
-- the tool was exercised before per-benchmark analyses — the empirical
-- counterpart to the unit-test suite. Each row is one benchmark; the
-- aggregate over all rows is the cross-suite footprint quoted in §3.
--
-- Columns:
--   stores           total store events captured
--   buffers          distinct (alloc_addr, generation) tracked allocations
--   call_sites       distinct allocation stack traces (proxy for source-level
--                    allocation sites exercised)
--   distinct_sizes   distinct alloc_size values seen (size diversity)
--   bytes_addressed  sum of alloc_size over distinct buffers — total
--                    addressable bytes the tool tracked end-to-end
WITH per_buf AS (
    SELECT
        bench,
        alloc_addr,
        generation,
        ANY_VALUE(alloc_size) AS sz
    FROM all_stores
    GROUP BY bench, alloc_addr, generation
)
SELECT
    s.bench,
    COUNT(*)::BIGINT                            AS stores,
    (SELECT COUNT(*) FROM per_buf b
       WHERE b.bench = s.bench)::BIGINT         AS buffers,
    COUNT(DISTINCT alloc_stack)::BIGINT         AS call_sites,
    COUNT(DISTINCT alloc_size)::BIGINT          AS distinct_sizes,
    (SELECT SUM(sz) FROM per_buf b
       WHERE b.bench = s.bench)::BIGINT         AS bytes_addressed
FROM all_stores s
GROUP BY s.bench
ORDER BY stores DESC;
