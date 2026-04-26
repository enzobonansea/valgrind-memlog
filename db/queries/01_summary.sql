-- Per-benchmark totals: stores, distinct allocations, breakdown by alignment type.
SELECT
    bench,
    COUNT(*)                                              AS stores,
    COUNT(DISTINCT (alloc_addr, generation))              AS allocations,
    SUM(alloc_type = '64bits')::BIGINT                    AS stores_64bits,
    SUM(alloc_type = '32bits')::BIGINT                    AS stores_32bits,
    SUM(alloc_type = 'object')::BIGINT                    AS stores_object,
    SUM(value = 0)::DOUBLE / COUNT(*)                     AS frac_zero_value
FROM all_stores
GROUP BY bench
ORDER BY stores DESC;
