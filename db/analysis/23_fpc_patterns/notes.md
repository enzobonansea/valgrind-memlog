# 23_fpc_patterns — FPC pattern coverage per (bench, alloc_type)

`result.csv`: per (bench, alloc_type), share of stores matching each FPC
[Burtscher 2009] pattern: `pct_zero`, `pct_sign{4,8,16,32}` (sign-extended
narrow integers), `pct_high_zero_low16`, `pct_repeating_byte`, plus the OR-
union `pct_any_pattern` as an upper bound on FPC's lossless coverage.

`figure.svg`: heatmap, rows = (bench · alloc_type), cols = pattern, last
column is the union. Reads as a per-bench compressibility budget under a
classic float-pattern compressor. Pairs with 22_bdi_compression (range-
based deltas) and 31_cacheline_homogeneity (line-level homogeneity).
