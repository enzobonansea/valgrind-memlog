# 03_size_distribution — allocation size histogram

`result.csv`: one row per `(bench, size_bucket_bytes)` (size buckets are
power-of-two). `allocations` = count of distinct `(alloc_addr, generation)`
landing in that bucket.

`figure.svg`: log-log CCDF — x = allocation size, y = number of allocations
of that size or larger, one line per bench. The tail behaviour separates
benches with a few enormous buffers (left-heavy curves drop fast) from
benches with broad heavy-tailed distributions.
