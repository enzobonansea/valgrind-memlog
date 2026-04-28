# 33_validation_robustness — Validation §3 edge-case spread

`result.csv`: per bench, allocation-size span (`min_size`, `median_size`,
`max_size`), `max_generation` (deepest reuse), `buffers_reused` count,
`distinct_alignment_classes`, `max_offset` reached.

`figure.svg`: per-bench horizontal whisker on a log-x axis from min_size
to max_size, marker at median_size, ordered by ascending median. Argues
the test set spans the realistic size range; not a narrow band.
