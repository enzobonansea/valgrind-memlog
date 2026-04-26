-- Heap addresses that get reused (generation > 1) — typical for pool / freelist
-- allocators. Useful for spotting buffers that the allocator hands back
-- repeatedly, even if each generation is short-lived.
SELECT
    bench,
    printf('0x%x', alloc_addr) AS addr,
    MAX(generation)            AS max_generation,
    SUM(alloc_size) / NULLIF(MAX(generation), 0) AS avg_size,
    COUNT(*)                   AS total_stores
FROM all_stores
GROUP BY bench, alloc_addr
HAVING MAX(generation) > 1
ORDER BY max_generation DESC, total_stores DESC
LIMIT 20;
