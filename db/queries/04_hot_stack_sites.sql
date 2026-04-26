-- Hottest allocation call sites by stores written.
-- Groups by the first 3 frames of the stack so semantically-identical sites
-- (e.g. same `operator new` chain) collapse together.
SELECT
    bench,
    array_to_string(string_split(alloc_stack, chr(10))[1:3], chr(10)) AS site,
    COUNT(*)                                          AS stores,
    COUNT(DISTINCT (alloc_addr, generation))          AS allocs,
    SUM(alloc_size)::BIGINT                           AS total_bytes
FROM all_stores
GROUP BY bench, site
ORDER BY stores DESC
LIMIT 15;
