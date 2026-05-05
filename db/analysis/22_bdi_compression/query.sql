-- @set threads 2
-- @set memory_limit 32GB
-- @set watch_spill_gb 130
-- BDI (Base+Delta) cache-line compressibility per (bench, alloc_type).
-- BDI [Pekhimenko 2012] partitions a 64-byte cache line into elements,
-- picks one as a base, and stores the rest as fixed-width signed deltas
-- relative to the base. A line is compressible at delta-width K if the
-- range of element values inside the line fits in K bits.
--
-- Operating on the last-write snapshot per buffer, we build per-cache-line
-- (64 B) groups and report the fraction of lines whose value range fits
-- within K = 8 / 16 / 32 bits. Only lines with at least 2 distinct slots
-- are counted (single-slot lines are trivially compressible).
--
-- Caveat: BDI was designed for integer / pointer values. When the underlying
-- bytes are IEEE-754 bit patterns, the metric overestimates compressibility
-- for arrays of small magnitudes (where high bits agree) and underestimates
-- for arrays whose values share an exponent but differ in the low mantissa.
-- Pair with 23_fpc_patterns.sql for a float-pattern-aware view.
-- Per-bench iteration bounds window state to one parquet at a time.
-- Snapshot extraction uses arg_max(value, rn) (rn = parquet file_row_number
-- from the view) instead of the earlier ROW_NUMBER OVER () + QUALIFY
-- pattern, whose global window forced a spill-heavy materialise.
WITH snapshot AS (
    SELECT alloc_type, alloc_addr, generation, "offset",
        arg_max(value, rn) AS value
    FROM {bench}
    WHERE alloc_type IN ('32bits', '64bits')
    GROUP BY alloc_type, alloc_addr, generation, "offset"
),
per_line AS (
    SELECT alloc_type, alloc_addr, generation,
        "offset" // 64                  AS line_id,
        COUNT(*)                       AS slots,
        MAX(value) - MIN(value)        AS rng
    FROM snapshot
    GROUP BY alloc_type, alloc_addr, generation, "offset" // 64
)
SELECT
    '{bench}' AS bench,
    alloc_type,
    COUNT(*)::BIGINT                                              AS lines,
    SUM(slots = 1)::BIGINT                                        AS trivial_lines,
    SUM(slots >= 2 AND rng < (1::UBIGINT << 8))::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)           AS bdi8_frac,
    SUM(slots >= 2 AND rng < (1::UBIGINT << 16))::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)           AS bdi16_frac,
    SUM(slots >= 2 AND rng < (1::UBIGINT << 32))::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE slots >= 2), 0)           AS bdi32_frac,
    AVG(rng) FILTER (WHERE slots >= 2)                            AS mean_range
FROM per_line
GROUP BY alloc_type
ORDER BY alloc_type;
