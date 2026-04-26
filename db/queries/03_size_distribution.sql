-- Allocation-size distribution per benchmark, in power-of-two buckets.
WITH per_alloc AS (
    SELECT bench, alloc_addr, generation, ANY_VALUE(alloc_size) AS alloc_size
    FROM all_stores
    GROUP BY bench, alloc_addr, generation
)
SELECT
    bench,
    1 << CAST(FLOOR(LOG2(alloc_size)) AS INTEGER) AS size_bucket_bytes,
    COUNT(*) AS allocations
FROM per_alloc
GROUP BY bench, size_bucket_bytes
ORDER BY bench, size_bucket_bytes;
