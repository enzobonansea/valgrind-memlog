# 07_reused_allocations — top reused heap addresses

`result.csv`: 20 rows globally. Columns: `bench`, `addr`, `max_generation`
(highest reuse count for that address), `avg_size`, `total_stores`. Picks
out allocator hotspots — addresses that get malloc'd / free'd thousands of
times during the run.

`figure.svg`: log-log scatter, x = total stores landed at the address,
y = max_generation, point colour = bench. A point in the upper-right is
both heavily reused AND heavily written — strong candidate for a custom
slab / pool allocator.
