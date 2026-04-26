-- Stored-value classification per benchmark / alloc type.
--   zero        : value == 0 (zero-init or scrubbed memory)
--   pointer_ish : top byte is 0x00 and magnitude > 2^32 (typical x86_64 user pointer)
--   double_ish  : reinterpreted as IEEE-754 double, exponent lies in [0x380, 0x47f]
--                 — i.e. magnitudes ~1e-38 .. 1e+38, the realistic float/double range
SELECT
    bench,
    alloc_type,
    SUM(value = 0)::BIGINT                                            AS zero,
    SUM(value <> 0 AND (value >> 56) = 0
        AND value > (1::UBIGINT << 32))::BIGINT                       AS pointer_ish,
    SUM(((value >> 52) & 2047) BETWEEN 896 AND 1151)::BIGINT          AS double_ish,
    COUNT(*)::BIGINT                                                  AS total
FROM all_stores
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
