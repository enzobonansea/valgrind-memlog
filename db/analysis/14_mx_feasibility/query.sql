-- MX (microscaling) format feasibility per (bench, alloc_type).
-- Mirrors figs-generators/analyze_fp8_mx.py.
--
-- MX encodes a block of N consecutive values as a shared scale (E8M0,
-- the max exponent in the block) plus per-element low-precision mantissas
-- (e.g. FP8 E4M3 with the shared scale stripped out). A block is
-- "MX-viable" when the unbiased exponent spread across its elements is at
-- most THRESHOLD; if the spread exceeds THRESHOLD the low-precision
-- mantissas can't represent the smallest values without underflow.
--
-- Defaults below match analyze_fp8_mx.py:
--   block size = 32   (OCP MX standard)
--   threshold  = 8    (MXFP8: E4M3 has 4 exponent bits, ~8 bits of headroom
--                      after one is used as bias)
--
-- We compute on the LAST-WRITE snapshot per (alloc_addr, generation,
-- offset), matching the paper's methodology — the buffer's final state is
-- what an offline conversion would observe. Zero / denormal / NaN / Inf
-- contribute no exponent and don't constrain the spread.
--
-- Per-bench iteration: a global ROW_NUMBER() over all_stores blew DuckDB's
-- spill budget on the silent-stores query (same pattern). Running per bench
-- bounds the window state to one parquet at a time.
--
-- Ordering note: ROW_NUMBER() OVER () enumerates rows in physical scan
-- order, which preserves the temporal store order within each
-- (alloc_addr, generation) inside this bench.
WITH numbered AS (
    SELECT *, ROW_NUMBER() OVER () AS rn
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
),
snapshot AS (
    SELECT alloc_type, alloc_addr, generation, "offset", value
    FROM numbered
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY alloc_addr, generation, "offset"
        ORDER BY rn DESC) = 1
),
indexed AS (
    SELECT *,
        (ROW_NUMBER() OVER (
            PARTITION BY alloc_addr, generation
            ORDER BY "offset") - 1) / 32 AS block_id
    FROM snapshot
),
exped AS (
    SELECT alloc_type, alloc_addr, generation, block_id,
        CASE
            WHEN value = 0 THEN NULL
            WHEN alloc_type = '64bits'
                AND ((value >> 52) & 2047) IN (0, 2047) THEN NULL
            WHEN alloc_type = '32bits'
                AND ((value >> 23) & 255) IN (0, 255)   THEN NULL
            WHEN alloc_type = '64bits' THEN ((value >> 52) & 2047)::INT
            WHEN alloc_type = '32bits' THEN ((value >> 23) & 255)::INT
        END AS exp_bits
    FROM indexed
),
spreads AS (
    SELECT alloc_type, alloc_addr, generation, block_id,
        MAX(exp_bits) - MIN(exp_bits) AS spread,
        COUNT(exp_bits)               AS valid_n
    FROM exped
    GROUP BY alloc_type, alloc_addr, generation, block_id
)
SELECT
    '{bench}' AS bench,
    alloc_type,
    COUNT(*)::BIGINT                                       AS blocks,
    SUM(valid_n < 2 OR spread <= 8)::BIGINT                AS viable_blocks,
    SUM(valid_n < 2 OR spread <= 8)::DOUBLE
        / NULLIF(COUNT(*), 0)                              AS viable_frac,
    AVG(spread) FILTER (WHERE valid_n >= 2)                AS mean_spread,
    QUANTILE_CONT(spread, 0.5) FILTER (WHERE valid_n >= 2) AS median_spread,
    MAX(spread)                                            AS max_spread
FROM spreads
GROUP BY alloc_type
ORDER BY alloc_type;
