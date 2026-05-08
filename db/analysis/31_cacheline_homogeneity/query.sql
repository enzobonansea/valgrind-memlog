-- @set threads 1
-- @set memory_limit 22GB
-- @set watch_spill_gb 200
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
-- Per-bench iteration bounds window state to one parquet at a time.
-- Snapshot extraction uses arg_max(value, rn) (rn = parquet file_row_number
-- from the view) instead of the earlier ROW_NUMBER OVER () + QUALIFY
-- pattern, whose global window forced a spill-heavy materialise.
-- "Homogeneous" is encoded as MIN(x) = MAX(x) instead of
-- COUNT(DISTINCT x) = 1: the former keeps O(1) state per group, the
-- latter a hash set per group, which OOM'd the 16GB buffer pool on
-- bwaves (millions of lines × 4 distinct-set columns).
--
-- The snapshot key is (alloc_type, alloc_addr, "offset") — generation
-- is intentionally collapsed. cam4 reuses the same address across ~6
-- generations on average, blowing the per-cell cardinality up to ~700M
-- in the 64-bit half (~30 GB hash-table state); arg_max didn't spill
-- cleanly and OOM'd at both the 16GB and bumped-22GB caps. Dropping
-- generation gives "physical-address current content" semantics rather
-- than "per-buffer final state": for each (alloc_type, alloc_addr,
-- offset) we keep the latest write across all reuses of that address.
-- This matches what a real cache compressor sees — a physical line
-- holds whatever was most recently written there, regardless of which
-- logical buffer owned it. Cardinality drops ~6× on cam4 (~100M cells)
-- and the snapshot fits comfortably in the 22GB cap.
WITH snapshot AS (
    SELECT alloc_type, alloc_addr, "offset",
        arg_max(value, rn) AS value
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
    GROUP BY alloc_type, alloc_addr, "offset"
),
per_line AS (
    SELECT alloc_type, alloc_addr,
        "offset" // 64                                             AS line_id,
        COUNT(*)                                                   AS slots,
        MIN(value >> 32) = MAX(value >> 32)                        AS homog_high32,
        MIN(value >> 48) = MAX(value >> 48)                        AS homog_high16,
        MIN(value >> 56) = MAX(value >> 56)                        AS homog_high8,
        MIN(CASE alloc_type
                WHEN '64bits' THEN ((value >> 52) & 2047)
                WHEN '32bits' THEN ((value >> 23) & 255)
            END) =
        MAX(CASE alloc_type
                WHEN '64bits' THEN ((value >> 52) & 2047)
                WHEN '32bits' THEN ((value >> 23) & 255)
            END)                                                   AS homog_exp
    FROM snapshot
    GROUP BY alloc_type, alloc_addr, "offset" // 64
)
SELECT
    '{bench}' AS bench,
    alloc_type,
    COUNT(*) FILTER (WHERE slots >= 2)::BIGINT                     AS lines,
    SUM((slots = 1)::INT)::BIGINT                                  AS trivial_lines,
    AVG(slots)                                                     AS mean_slots_per_line,
    SUM((slots >= 2 AND homog_high32)::INT)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)            AS frac_homog_high32,
    SUM((slots >= 2 AND homog_high16)::INT)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)            AS frac_homog_high16,
    SUM((slots >= 2 AND homog_high8)::INT)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)            AS frac_homog_high8,
    SUM((slots >= 2 AND homog_exp)::INT)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)            AS frac_homog_exp
FROM per_line
GROUP BY alloc_type
ORDER BY alloc_type;
