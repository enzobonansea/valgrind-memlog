# 29_bit_plane_entropy — per-bit Shannon entropy of stored values

`result.csv`: 64 rows per (bench, alloc_type) — entropy of each bit
position across all stores. `p_one` is the bias toward 1 in that position;
`entropy = H(p_one)` ranges 0 (constant) to 1 (uniform random).

`figure.svg`: line plot, x = bit position 0..63, y = entropy. Two panels
(64bits / 32bits). Low-entropy bit positions are predictable and compress
well (typically the high bits of small values, the sign and high exponent
bits of FP, and trailing mantissa bits of low-precision FP). High-entropy
positions are near-random.

Predicts ratios for bit-plane compressors (Mokey, KIM 2016) and reveals
the structural redundancy in raw store traffic.
