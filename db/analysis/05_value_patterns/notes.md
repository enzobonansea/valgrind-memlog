# 05_value_patterns — exact bit-pattern shares per (bench, alloc_type)

`result.csv`: `zero`, `nonzero_top_byte_zero`, `nonzero_top_byte_nonzero`
(disjoint partition over `total`), plus `exp_field_normal_f64` as a
secondary IEEE-754-bit-position fact. Strict bit-pattern facts only — NO
claim about whether values are float / int / pointer.

`figure.svg`: 100% stacked horizontal bars, one panel per alloc_type
(64bits / 32bits / object), colours = the disjoint partition. Captures the
share of stores whose magnitude is small (top byte zero) vs not. Pairs
naturally with 06_alignment (alignment of stores) and 12_format_feasibility
(precision needed) when arguing for compression schemes.
