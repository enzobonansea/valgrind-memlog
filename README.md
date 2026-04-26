# Memlog

Valgrind tool that logs writes to large memory buffers, plus a pipeline
that turns those raw logs into queryable parquet.

## Pipeline

```
    binary or SPEC app
          │
          │   1.  valgrind --tool=memlog
          ▼
    memlog.PID.log                     (raw text log, often GiB+)
          │
          │   2.  tools/parser.py
          ▼
    memlog.PID.log.parsed/             (one .stores file per allocation)
          │
          │   3.  tools/compress.sh
          ▼
    raw/<bench>.tar.xz                 (parallel xz via pixz)
          │
          │   4.  tools/to_parquet.py
          ▼
    db/<bench>.parquet                 (one row per store, dict-encoded)
    db/memlog.duckdb                   (views: <bench> + all_stores)
          │
          │   5.  duckdb / db/queries/*.sql
          ▼
    results
```

Each stage is a separate tool; they're glued together so you can also enter
the pipeline at any step (e.g. drop a `.tar.xz` into `raw/` and skip the
first three).

### 1. Run a binary under memlog

`memlog` is a Valgrind tool that records every store to allocations larger
than `--min-block-size`. Output is a single text log.

```bash
valgrind --tool=memlog --min-block-size=4096 \
         --log-file=memlog.PID.log -- <binary> [args]
```

For SPEC CPU2017 inside the container, use the menu / `analyze.sh` wrapper.
For an arbitrary binary, point Valgrind at it directly. Expect logs of GiB
to TiB scale on real workloads.

### 2. Parse the log into per-allocation `.stores` files

`tools/parser.py` walks the log streamingly and writes one `.stores` file
per allocation site, named `0x<addr>_<size>_<type>_<gen>.stores` where
`<type>` is `64bits`, `32bits`, or `object` (alignment-derived) and `<gen>`
is the reuse counter for that address.

```bash
tools/parser.py memlog.PID.log
# -> memlog.PID.log.parsed/0x<addr>_<size>_<type>_<gen>.stores  (one per alloc)
```

Each `.stores` file starts with `# <stack frame>` lines for the allocation
site, then `offset:0xvalue` lines for every store.

### 3. Compress the parsed tree for transfer / storage

```bash
tools/compress.sh 523.xalancbmk_r.test    # -> 523.xalancbmk_r.test.tar.xz
```

Uses `pixz` for parallel xz compression. Drop the resulting `.tar.xz`
under `raw/<bench>.tar.xz`. (Pre-built archives can also be pulled with
`rclone`.)

### 4. Convert `raw/*.tar.xz` → parquet + DuckDB

```bash
pip install --user pyarrow tqdm duckdb        # one-time
sudo apt install pixz                          # optional, parallel decompression
python3 tools/to_parquet.py
```

What `to_parquet.py` does, per archive:

- streams the `.tar.xz` straight through (no temp directory, fits archives
  larger than free disk),
- parses every `.stores` member in flight,
- writes `db/<bench>.parquet` — one row per store, dictionary-encoded
  `alloc_type` and `alloc_stack` so the file size is dominated by data not
  metadata,
- (re)builds `db/memlog.duckdb` with one view per benchmark plus an
  `all_stores` union view (`bench, alloc_addr, alloc_size, alloc_type,
  generation, alloc_stack, offset, value`).

A tqdm bar tracks compressed bytes consumed; the postfix shows live
allocation / store counts. `pixz` is auto-detected for parallel
decompression and is recommended for the 100 GB+ archives.

### 5. Query

Eight ready-made queries live under `db/queries/` (summary, hotspots, size
distribution, hot stack sites, value-bit patterns, alignment, reuse,
coverage). All target the `all_stores` view, so they work across whichever
benchmarks you've converted.

```bash
python3 -c "import duckdb; print(duckdb.connect('db/memlog.duckdb', read_only=True).execute(open('db/queries/01_summary.sql').read()).fetchdf().to_string(index=False))"
```

Or use the DuckDB CLI / your tool of choice — the parquet files are the
canonical artifact, the `.duckdb` is just a thin wrapper of views.

## Quick Start (Docker, end-to-end)

```bash
# 1. Place SPEC CPU2017 ISO in repo root
cp /path/to/cpu2017-1.1.9.iso .

# 2. Build the analysis image
./build/install.sh

# 3. Run; pick a SPEC app from the interactive menu
docker run -it --rm memlog:latest
```

Inside the container, `analyze.sh` does steps 1–2 (valgrind + parser).
Steps 3–5 (compress, parquet, query) run on the host.

## What memlog tracks

- Allocations above `--min-block-size` (default 4096 bytes)
- Every store into those allocations: address, value, byte offset
- Per-allocation alignment classification: `64bits` / `32bits` / `object`

## Project layout

```
build/      # build scripts
examples/   # example programs
runtime/    # in-container scripts (analyze.sh, menu.sh)
tools/      # parser.py, compress.sh / decompress.sh, to_parquet.py
spec/       # SPEC CPU configs (memlog-*, lackey, native)
valgrind/   # vendored valgrind + memlog source
raw/        # *.tar.xz inputs (gitignored)
db/         # *.parquet + memlog.duckdb outputs (gitignored)
db/queries/ # example SQL against the all_stores view
```
