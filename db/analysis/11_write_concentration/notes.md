# 11_write_concentration — top-N buffers needed for X% of stores

`result.csv`: per bench, smallest N such that the top-N buffers absorb 50 /
80 / 90 / 95 / 99 % of total stores.

`figure.svg`: per-bench dot plot, y-axis is bench, x-axis is N (log).
Tight clusters on the left = highly concentrated workload (a handful of
buffers carry almost everything). Wide spreads = diffuse traffic. Pairs
with 02_top_allocations to argue for per-buffer optimisation.
