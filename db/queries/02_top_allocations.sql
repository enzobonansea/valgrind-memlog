-- Top 20 individual allocations by store count — the buffers that absorb the
-- most floating-point traffic.
SELECT
    bench,
    printf('0x%x', alloc_addr) AS addr,
    alloc_size,
    alloc_type,
    generation,
    COUNT(*)                   AS stores,
    COUNT(DISTINCT "offset")   AS unique_offsets,
    ROUND(COUNT(*) / NULLIF(alloc_size, 0)::DOUBLE, 2) AS stores_per_byte
FROM all_stores
GROUP BY bench, alloc_addr, alloc_size, alloc_type, generation
ORDER BY stores DESC
LIMIT 20;
