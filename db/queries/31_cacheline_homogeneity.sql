-- Compressed-cache-line homogeneity per (bench, alloc_type). For each
-- 64-byte aligned window in the last-write snapshot of each buffer we
-- check whether all stored values share their high bits — in which case a
-- compressed-cache design (Touche, Buddy Compression, Yacc) can fold the
-- whole line into a small encoding plus per-slot deltas.
--
-- For each line (64 B aligned, by `offset / 64`), with at least 2
-- distinct slots populated:
--   homog_high32        all values have identical upper 32 bits
--   homog_high16        all values have identical upper 16 bits
--   homog_high8         all values have identical upper 8 bits
--   homog_exp           all values share the same IEEE-754 biased exponent
--                       (a useful proxy for FPC / float-line compressors)
--
-- Per (bench, alloc_type) we report what fraction of lines are homogeneous
-- under each criterion. High homog_exp ⇒ float-aware line compressors
-- give big wins. High homog_high16 ⇒ even byte-level base+delta works.
--
-- Citations: Hajinazar 2021 ASPLOS (Touche); Choukse 2020 ISCA (Buddy
-- Compression); Park 2023 ISCA (Yacc); Tsai 2020 ISCA (CompressPoints).
WITH numbered AS (
    SELECT *, ROW_NUMBER() OVER () AS rn
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits')
),
snapshot AS (
    SELECT bench, alloc_type, alloc_addr, generation, "offset", value
    FROM numbered
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY bench, alloc_addr, generation, "offset"
        ORDER BY rn DESC) = 1
),
per_line AS (
    SELECT bench, alloc_type, alloc_addr, generation,
        "offset" / 64                                  AS line_id,
        COUNT(*)                                       AS slots,
        COUNT(DISTINCT value >> 32)                    AS distinct_high32,
        COUNT(DISTINCT value >> 48)                    AS distinct_high16,
        COUNT(DISTINCT value >> 56)                    AS distinct_high8,
        COUNT(DISTINCT
            CASE alloc_type
                WHEN '64bits' THEN ((value >> 52) & 2047)
                WHEN '32bits' THEN ((value >> 23) & 255)
            END
        )                                              AS distinct_exp
    FROM snapshot
    GROUP BY bench, alloc_type, alloc_addr, generation, "offset" / 64
)
SELECT
    bench, alloc_type,
    COUNT(*) FILTER (WHERE slots >= 2)::BIGINT                  AS lines,
    SUM(slots = 1)::BIGINT                                      AS trivial_lines,
    AVG(slots)                                                  AS mean_slots_per_line,
    SUM(slots >= 2 AND distinct_high32 = 1)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)         AS frac_homog_high32,
    SUM(slots >= 2 AND distinct_high16 = 1)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)         AS frac_homog_high16,
    SUM(slots >= 2 AND distinct_high8 = 1)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)         AS frac_homog_high8,
    SUM(slots >= 2 AND distinct_exp = 1)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)         AS frac_homog_exp
FROM per_line
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
