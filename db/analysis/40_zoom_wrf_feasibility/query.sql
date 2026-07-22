-- Zoom into wrf's individual buffers for reduced-precision representability
-- (Figure 6 in the paper). This analysis REUSES 36_per_buffer_feasibility
-- -- it does NOT re-run the trailing-zero pass. result.csv is
-- 36_per_buffer_feasibility/result.csv restricted to `bench = wrf` and
-- joined to the per-buffer allocation site produced by the query below.
--
-- The only parquet-touching step is this cheap lookup: alloc_stack is
-- constant within an (alloc_addr, generation), so a bare GROUP BY (no
-- window, no per-store scan of the string) yields one row per buffer.
-- figure.py then merges it with the reused Q36 rows and reduces
-- alloc_stack to its first non-allocator frame using the same regex as
-- 21_per_function_silent (the `site` column). See notes.md.
SELECT
    printf('0x%x', alloc_addr) AS addr,
    generation,
    any_value(alloc_stack)     AS alloc_stack
FROM 'data/wrf.parquet'
GROUP BY alloc_addr, generation;
