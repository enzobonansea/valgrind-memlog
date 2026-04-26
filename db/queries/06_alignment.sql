-- Store-offset alignment within allocations: how often offsets land on
-- 8-byte / 4-byte / unaligned boundaries, broken out per alloc_type.
SELECT
    bench,
    alloc_type,
    SUM("offset" % 8 = 0)::BIGINT AS aligned_8B,
    SUM("offset" % 8 = 4)::BIGINT AS aligned_4B_only,
    SUM("offset" % 4 <> 0)::BIGINT AS unaligned,
    COUNT(*)::BIGINT               AS total
FROM all_stores
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
