# 06_alignment — store-offset alignment per (bench, alloc_type)

`result.csv`: per (bench, alloc_type), counts of stores whose offset within
the allocation is `aligned_8B`, `aligned_4B_only`, or `unaligned`.

`figure.svg`: 100% stacked horizontal bars per (bench, alloc_type), faceted
by alloc_type. Direct input for compression-scheme designers: schemes that
require aligned access can quote the share of traffic they can cover
without falling back to a slow path.
