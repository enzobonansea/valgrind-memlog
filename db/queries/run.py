#!/usr/bin/env python3
"""Run a query (or every query) against db/memlog.duckdb and export the result
as CSV under db/results/.

Usage:
    db/queries/run.py                       # runs all NN_*.sql in numeric order
    db/queries/run.py 01_summary.sql        # single query (bare name or path)

Per-bench mode: if a .sql file contains the literal token `{bench}`, the harness
runs it once per bench (substituting the bench name), then concatenates the
results. Use this for queries whose hash-aggregate state would explode if run
against the global `all_stores` view. The substituted name resolves to that
bench's view (e.g., `blender`), so write `FROM {bench}` and add a literal
`'{bench}' AS bench` if you need the bench column in the output.

Output: db/results/<query-stem>.csv (one file per query)."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

QUERIES_DIR = Path(__file__).resolve().parent
DB_DIR      = QUERIES_DIR.parent
DATA_DIR    = DB_DIR / "data"
DB_PATH     = DATA_DIR / "memlog.duckdb"
RESULTS_DIR = DB_DIR / "results"
TMP_DIR     = DB_DIR / ".duckdb_tmp"

# 32 GB RAM, 8 GB swap, 66 GB of parquet behind `all_stores`. Without spill
# config, hash-aggregates on the bigger benches OOM-kill the process before
# DuckDB can react. Cap memory below the kernel's OOM trigger and point spill
# at the data disk (~500 GB free).
MEMORY_LIMIT = "24GB"
# Fewer threads = bigger per-thread hash-aggregate budget, which lets DuckDB
# hit the spill threshold instead of fragmenting memory across partitions.
# We're disk-bound on these queries, not CPU-bound.
THREADS      = 4


def resolve_query(arg: Path) -> Path:
    """Accept either a path to a .sql file or a bare filename in db/queries/."""
    if arg.is_file():
        return arg.resolve()
    candidate = QUERIES_DIR / arg.name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(arg)


def list_benches(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Bench names = parquet file stems, in alphabetical order."""
    return sorted(p.stem for p in DATA_DIR.glob("*.parquet"))


def run_query(con: duckdb.DuckDBPyConnection, query_path: Path) -> Path:
    sql = query_path.read_text()
    out_path = RESULTS_DIR / f"{query_path.stem}.csv"
    t0 = time.perf_counter()

    if "{bench}" in sql:
        frames: list[pd.DataFrame] = []
        for bench in list_benches(con):
            frames.append(con.execute(sql.format(bench=bench)).fetchdf())
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    else:
        df = con.execute(sql).fetchdf()

    df.to_csv(out_path, index=False)
    elapsed = time.perf_counter() - t0
    print(f"[{query_path.name}] {len(df)} row(s) in {elapsed:.2f}s -> {out_path}")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", type=Path,
                    help="single .sql file to run (bare filename or path); "
                         "if omitted, runs every NN_*.sql in numeric order")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"error: {DB_PATH} not found — run tools/to_parquet.py first",
              file=sys.stderr)
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.query is not None:
        try:
            queries = [resolve_query(args.query)]
        except FileNotFoundError as e:
            print(f"error: {e} not found", file=sys.stderr)
            return 1
    else:
        queries = sorted(QUERIES_DIR.glob("[0-9][0-9]_*.sql"))
        if not queries:
            print(f"error: no NN_*.sql files in {QUERIES_DIR}", file=sys.stderr)
            return 1

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute(f"PRAGMA memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"PRAGMA temp_directory='{TMP_DIR}'")
    con.execute(f"PRAGMA threads={THREADS}")
    con.execute("PRAGMA preserve_insertion_order=false")
    failures = 0
    try:
        for q in queries:
            try:
                run_query(con, q)
            except Exception as e:
                failures += 1
                print(f"[{q.name}] FAILED: {e}", file=sys.stderr)
    finally:
        con.close()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
