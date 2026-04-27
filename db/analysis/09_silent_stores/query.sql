-- Silent stores: writes that put the same value back into the same
-- (alloc_addr, generation, offset) location as the most recent prior write.
-- Useful as an upper bound on how much store traffic a "silent-store
-- elimination" optimization could remove.
--
-- Ordering note: the parquet preserves the temporal order of stores within
-- each (alloc_addr, generation), because to_parquet.py emits .stores rows
-- in the same order parser.py wrote them. ROW_NUMBER() OVER () enumerates
-- in physical scan order, so PARTITION BY (bench, alloc, gen, offset)
-- ORDER BY rn reconstructs the per-location store sequence.
WITH numbered AS (
    SELECT *, ROW_NUMBER() OVER () AS rn FROM all_stores
),
lagged AS (
    SELECT
        bench, alloc_type, value,
        LAG(value) OVER (
            PARTITION BY bench, alloc_addr, generation, "offset"
            ORDER BY rn
        ) AS prev_value
    FROM numbered
)
SELECT
    bench, alloc_type,
    COUNT(*) FILTER (WHERE prev_value IS NOT NULL)              AS stores_with_prev,
    COUNT(*) FILTER (WHERE prev_value = value)                  AS silent,
    COUNT(*) FILTER (WHERE prev_value = value)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE prev_value IS NOT NULL), 0) AS silent_frac
FROM lagged
GROUP BY bench, alloc_type
ORDER BY bench, alloc_type;
