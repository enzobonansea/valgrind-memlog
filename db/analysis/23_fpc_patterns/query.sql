-- FPC (Frequent Pattern Compression) coverage per (bench, alloc_type).
-- FPC [Burtscher 2009 / Alameldeen-Wood 2004] compresses a value by
-- detecting common bit patterns and encoding only the meaningful part
-- plus a small prefix tag. We approximate seven of the most useful
-- patterns and report what fraction of stored values match each:
--
--   zero               value is exactly 0
--   sign4              value fits in a 4-bit signed integer  (-8 .. 7)
--   sign8              fits in 8-bit signed                 (-128 .. 127)
--   sign16             fits in 16-bit signed
--   sign32             fits in 32-bit signed (only meaningful for 64bits)
--   high_zero_low16    upper 48 (or 16) bits are zero, low 16 bits arbitrary
--   repeating_byte     all bytes of the (32- or 64-bit) value are equal
--                      (e.g. 0x0000_0000, 0xFFFF_FFFF, 0xAAAA_AAAA)
--
-- The "any_pattern" column is a logical OR over the seven patterns and
-- represents an upper bound on FPC coverage. Real FPC implementations
-- pick a single best tag per value; this metric tells you the ceiling.
WITH classified AS (
    SELECT
        bench, alloc_type, value,
        CASE alloc_type
            WHEN '32bits' THEN value & ((1::UBIGINT << 32) - 1)
            ELSE          value
        END AS v
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits')
),
flagged AS (
    SELECT
        bench, alloc_type,
        v = 0                                                    AS zero,
        -- 4-bit signed in two's-complement of the relevant width
        (v < 8) OR (alloc_type = '32bits'
                    AND v >= ((1::UBIGINT << 32) - 8))
                OR (alloc_type = '64bits'
                    AND v >= (18446744073709551608::UBIGINT))    AS sign4,
        (v < 128) OR (alloc_type = '32bits'
                    AND v >= ((1::UBIGINT << 32) - 128))
                  OR (alloc_type = '64bits'
                    AND v >= (18446744073709551488::UBIGINT))    AS sign8,
        (v < 32768) OR (alloc_type = '32bits'
                    AND v >= ((1::UBIGINT << 32) - 32768))
                    OR (alloc_type = '64bits'
                    AND v >= (18446744073709518848::UBIGINT))    AS sign16,
        (alloc_type = '64bits'
            AND (v < (1::UBIGINT << 31)
                 OR v >= (18446744071562067968::UBIGINT)))       AS sign32,
        -- Top bits zero, low 16 arbitrary
        ((alloc_type = '32bits' AND (v >> 16) = 0)
         OR (alloc_type = '64bits' AND (v >> 16) = 0))           AS high_zero_low16,
        -- All-equal bytes
        CASE alloc_type
            WHEN '32bits' THEN
                (v & 255) = ((v >> 8) & 255)
                AND (v & 255) = ((v >> 16) & 255)
                AND (v & 255) = ((v >> 24) & 255)
            WHEN '64bits' THEN
                (v & 255) = ((v >> 8) & 255)
                AND (v & 255) = ((v >> 16) & 255)
                AND (v & 255) = ((v >> 24) & 255)
                AND (v & 255) = ((v >> 32) & 255)
                AND (v & 255) = ((v >> 40) & 255)
                AND (v & 255) = ((v >> 48) & 255)
                AND (v & 255) = ((v >> 56) & 255)
        END                                                       AS repeating_byte
    FROM classified
)
SELECT
    bench, alloc_type,
    COUNT(*)::BIGINT                                              AS total,
    SUM(zero)::DOUBLE             / COUNT(*)                      AS pct_zero,
    SUM(sign4)::DOUBLE            / COUNT(*)                      AS pct_sign4,
    SUM(sign8)::DOUBLE            / COUNT(*)                      AS pct_sign8,
    SUM(sign16)::DOUBLE           / COUNT(*)                      AS pct_sign16,
    SUM(sign32)::DOUBLE           / COUNT(*)                      AS pct_sign32,
    SUM(high_zero_low16)::DOUBLE  / COUNT(*)                      AS pct_high_zero_low16,
    SUM(repeating_byte)::DOUBLE   / COUNT(*)                      AS pct_repeating_byte,
    SUM(zero OR sign4 OR sign8 OR sign16 OR sign32
        OR high_zero_low16 OR repeating_byte)::DOUBLE / COUNT(*)  AS pct_any_pattern
FROM flagged
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
