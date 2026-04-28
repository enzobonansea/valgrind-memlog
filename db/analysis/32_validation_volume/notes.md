# 32_validation_volume — Validation §3 testing volume per benchmark

`result.csv`: one row per bench with the workload-size facts paper §3
quotes: `stores`, distinct `buffers`, distinct `call_sites`, distinct
`alloc_size` values, total bytes addressed.

`figure.svg`: three log-x horizontal-bar panels (stores / buffers / call
sites), shared bench order. Empirical counterpart to the 11-test unit
suite — it is the "we tested at SPEC scale" claim made visible.
