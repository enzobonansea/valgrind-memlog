# 04_hot_stack_sites — top 15 alloc-stack sites globally

`result.csv`: 15 rows. Columns: `bench`, `site` (multi-line valgrind-format
stack trace), `stores`, `allocs`, `total_bytes`. The top-15 across the whole
suite — a small set of malloc call sites absorbs the majority of FP store
traffic in the corpus.

`figure.svg`: horizontal log-x bar chart, label = `bench: <function>`
(function extracted as the first non-malloc frame), bar length = stores.
Points to where source-level annotations / per-site optimisation would land
the most benefit.
