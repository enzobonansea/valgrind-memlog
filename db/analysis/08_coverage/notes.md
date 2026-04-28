# 08_coverage — per-bench slot write density

`result.csv`: per (bench, alloc_type), the mean / min / max of
`unique_offsets * slot_bytes / alloc_size` (fraction of slots that ever
receive a store) plus mean writes per written slot.

`figure.svg`: scatter — x = avg coverage (log), y = avg writes per slot
(log), bubble area = number of allocations, colour = alloc_type. Quadrants
separate streaming/init benches (high coverage, low writes per slot) from
in-place update benches (high coverage, high writes) and sparse-poking
benches (low coverage).

Implementation: per-bench iteration with two-stage GROUP BY (offset →
alloc) so every operator spills cleanly.
