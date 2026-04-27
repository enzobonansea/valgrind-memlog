-- Stored-value bit-pattern shares per benchmark / alloc_type.
-- Every column is an exact share of the population — NO claims about whether
-- a given store's bytes are a float, an int, or a pointer. We only describe
-- the bit pattern itself.
--
-- The first three columns are a disjoint partition of `total`:
--   zero                         : value == 0 (zero-init / scrubbed memory)
--   nonzero_top_byte_zero        : value != 0 AND (value >> 56) == 0
--                                  i.e. magnitude fits in 56 bits unsigned
--   nonzero_top_byte_nonzero     : the rest
--
-- exp_field_normal_f64 is reported as a secondary fact (it overlaps the
-- partition above): share of values whose binary64 exponent field
-- ((value >> 52) & 0x7FF) lies in the IEEE normal-encoding range [1, 2046].
SELECT
    bench,
    alloc_type,
    SUM(value = 0)::BIGINT                                            AS zero,
    SUM(value <> 0 AND (value >> 56) = 0)::BIGINT                     AS nonzero_top_byte_zero,
    SUM(value <> 0 AND (value >> 56) <> 0)::BIGINT                    AS nonzero_top_byte_nonzero,
    SUM(((value >> 52) & 2047) BETWEEN 1 AND 2046)::BIGINT            AS exp_field_normal_f64,
    COUNT(*)::BIGINT                                                  AS total
FROM all_stores
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
