# 30_posit_fit — Posit-32 suitability profile

`result.csv`: per (bench, alloc_type), `frac_high_precision` /
`frac_mid_precision` / `frac_extreme` shares plus `mean_posit_useful_bits`.
"High-precision" = small unbiased exponent → posits give more mantissa
bits than IEEE-32 there.

`figure.svg`: horizontal bar of `frac_high_precision` per bench, faceted by
alloc_type. The benches with high bars in the 64bits panel are the ones
where posit-32 has a real precision advantage; the ones near zero are
extreme-magnitude or already-low-precision workloads.
