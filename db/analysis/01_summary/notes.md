# 01_summary — per-bench store totals

`result.csv`: one row per bench (24 rows). Columns: total `stores`, distinct
`allocations`, store counts split by `alloc_type` (64bits / 32bits / object),
`frac_zero_value`.

`figure.svg`: horizontal stacked bar (log x), 24 benches sorted by total
stores, segments coloured by alloc_type. Headline picture for the suite —
shows the >6 orders of magnitude dynamic range across benches, plus which
benches are dominated by 8-byte vs 4-byte vs object allocations.

Used as the *denominator* for `02_top_allocations/figure.py` (concentration
ratio) and is the natural lead figure of any paper section that needs to
introduce the workload mix.
