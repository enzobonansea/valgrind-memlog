# 30_posit_fit — Posit-32 suitability profile

`result.csv`: per (bench, alloc_type ∈ {32bits, 64bits}),
`frac_high_precision` / `frac_mid_precision` / `frac_extreme` shares plus
`mean_posit_useful_bits`. "High-precision" = small unbiased exponent →
posits give more mantissa bits than IEEE-32 there. `object` allocations
are excluded: posit-32 is an IEEE-754 float replacement, so the metric is
only meaningful where the stored value is interpreted as a float.

`figure.svg`: horizontal bar of `frac_high_precision` per bench, faceted by
alloc_type (64bits, 32bits). Benches with high bars in the 64bits panel
are the ones where posit-32 has a real precision advantage; the ones near
zero are extreme-magnitude or already-low-precision workloads.
