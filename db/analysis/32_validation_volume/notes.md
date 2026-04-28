# 32_validation_volume — Validation §3 testing volume per benchmark

`result.csv`: one row per bench with the workload-size facts paper §3
quotes: `stores`, distinct `buffers`, distinct `call_sites`, distinct
`alloc_size` values, total bytes addressed, `buffers_per_site`.

`buffers` ≠ `call_sites`: a buffer is one allocation (`alloc_addr`,
`generation`); a call site is one allocation stack trace. A `malloc`
in a loop is one call site producing many buffers, so
`buffers ≥ call_sites` and typically `buffers ≫ call_sites`. The
`buffers_per_site` ratio quantifies that reuse: perlbench is 1565×
(massive loop reuse), lbm/deepsjeng are 1× (one-shot setup), xz is
0.19× (more sites than live buffers — short-lived allocations).

`figure.svg`: two log-x panels, shared bench order. Left: `stores`.
Right: `buffers` and `call_sites` as grouped bars on a shared axis
with the per-site ratio annotated at the right edge — the bar gap is
the reuse story made visible. Empirical counterpart to the 11-test
unit suite — it is the "we tested at SPEC scale" claim made visible.
