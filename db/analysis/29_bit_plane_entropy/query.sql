-- Bit-plane Shannon entropy per (bench, alloc_type). For each bit position
-- 0..63 of the stored value we compute the probability that the bit is 1
-- and the corresponding binary entropy. Bit planes with entropy near 0 are
-- almost-constant and compressed away by bit-plane / sign-magnitude
-- compressors; planes near 1 are random and incompressible.
--
-- Bit-plane compression literature reports these numbers on synthetic DNN
-- weight matrices; this query produces them directly from real SPEC
-- workloads, with allocation-site provenance available via the bench
-- column (extend with alloc_stack if you want per-site planes).
--
-- Output is "tall": one row per (bench, alloc_type, bit_pos), with the
-- per-bit p_one and entropy ready to plot or join.
--
-- Citations: Kim 2016 IEEE Micro (Bit-Plane Compression); Lascorz 2023
-- ISCA (Mokey / Boveda); Eckert 2022 HPCA (bit-plane sparsity).
WITH agg AS (
    SELECT bench, alloc_type,
        COUNT(*)::BIGINT AS total,
        [
          SUM(((value >>  0) & 1)::BIGINT), SUM(((value >>  1) & 1)::BIGINT),
          SUM(((value >>  2) & 1)::BIGINT), SUM(((value >>  3) & 1)::BIGINT),
          SUM(((value >>  4) & 1)::BIGINT), SUM(((value >>  5) & 1)::BIGINT),
          SUM(((value >>  6) & 1)::BIGINT), SUM(((value >>  7) & 1)::BIGINT),
          SUM(((value >>  8) & 1)::BIGINT), SUM(((value >>  9) & 1)::BIGINT),
          SUM(((value >> 10) & 1)::BIGINT), SUM(((value >> 11) & 1)::BIGINT),
          SUM(((value >> 12) & 1)::BIGINT), SUM(((value >> 13) & 1)::BIGINT),
          SUM(((value >> 14) & 1)::BIGINT), SUM(((value >> 15) & 1)::BIGINT),
          SUM(((value >> 16) & 1)::BIGINT), SUM(((value >> 17) & 1)::BIGINT),
          SUM(((value >> 18) & 1)::BIGINT), SUM(((value >> 19) & 1)::BIGINT),
          SUM(((value >> 20) & 1)::BIGINT), SUM(((value >> 21) & 1)::BIGINT),
          SUM(((value >> 22) & 1)::BIGINT), SUM(((value >> 23) & 1)::BIGINT),
          SUM(((value >> 24) & 1)::BIGINT), SUM(((value >> 25) & 1)::BIGINT),
          SUM(((value >> 26) & 1)::BIGINT), SUM(((value >> 27) & 1)::BIGINT),
          SUM(((value >> 28) & 1)::BIGINT), SUM(((value >> 29) & 1)::BIGINT),
          SUM(((value >> 30) & 1)::BIGINT), SUM(((value >> 31) & 1)::BIGINT),
          SUM(((value >> 32) & 1)::BIGINT), SUM(((value >> 33) & 1)::BIGINT),
          SUM(((value >> 34) & 1)::BIGINT), SUM(((value >> 35) & 1)::BIGINT),
          SUM(((value >> 36) & 1)::BIGINT), SUM(((value >> 37) & 1)::BIGINT),
          SUM(((value >> 38) & 1)::BIGINT), SUM(((value >> 39) & 1)::BIGINT),
          SUM(((value >> 40) & 1)::BIGINT), SUM(((value >> 41) & 1)::BIGINT),
          SUM(((value >> 42) & 1)::BIGINT), SUM(((value >> 43) & 1)::BIGINT),
          SUM(((value >> 44) & 1)::BIGINT), SUM(((value >> 45) & 1)::BIGINT),
          SUM(((value >> 46) & 1)::BIGINT), SUM(((value >> 47) & 1)::BIGINT),
          SUM(((value >> 48) & 1)::BIGINT), SUM(((value >> 49) & 1)::BIGINT),
          SUM(((value >> 50) & 1)::BIGINT), SUM(((value >> 51) & 1)::BIGINT),
          SUM(((value >> 52) & 1)::BIGINT), SUM(((value >> 53) & 1)::BIGINT),
          SUM(((value >> 54) & 1)::BIGINT), SUM(((value >> 55) & 1)::BIGINT),
          SUM(((value >> 56) & 1)::BIGINT), SUM(((value >> 57) & 1)::BIGINT),
          SUM(((value >> 58) & 1)::BIGINT), SUM(((value >> 59) & 1)::BIGINT),
          SUM(((value >> 60) & 1)::BIGINT), SUM(((value >> 61) & 1)::BIGINT),
          SUM(((value >> 62) & 1)::BIGINT), SUM(((value >> 63) & 1)::BIGINT)
        ] AS ones_per_bit
    FROM all_stores
    WHERE alloc_type IN ('32bits', '64bits')
    GROUP BY bench, alloc_type
)
SELECT
    bench, alloc_type, total,
    bit_pos,
    ones_per_bit[bit_pos + 1]::DOUBLE / total          AS p_one,
    CASE
        WHEN ones_per_bit[bit_pos + 1] = 0
             OR ones_per_bit[bit_pos + 1] = total       THEN 0.0
        ELSE
            -(ones_per_bit[bit_pos + 1]::DOUBLE / total)
                * LOG2(ones_per_bit[bit_pos + 1]::DOUBLE / total)
            -((total - ones_per_bit[bit_pos + 1])::DOUBLE / total)
                * LOG2((total - ones_per_bit[bit_pos + 1])::DOUBLE / total)
    END                                                AS entropy
FROM agg, generate_series(0, 63) AS s(bit_pos)
ORDER BY bench, alloc_type, bit_pos;
