#!/usr/bin/env python3
"""Run an analysis (or all) against db/data/memlog.duckdb.

Vertical-slice layout: each analysis lives in db/analysis/<NN_name>/ with
a query.sql, a result.csv (produced here), and an optional figure.py +
figure.svg. This script reads query.sql and writes result.csv next to it.

Usage:
    db/run.py                   # run every db/analysis/NN_*/query.sql in order
    db/run.py 01_summary        # run a single analysis (folder name or path)

Per-bench mode: if a query.sql contains the literal token `{bench}`, the
harness runs it once per bench (substituting the bench name), then concats
the results. Use this for queries whose hash-aggregate state would explode
if run against the global `all_stores` view. The substituted name resolves
to that bench's view (e.g., `blender`), so write `FROM {bench}` and add a
literal `'{bench}' AS bench` if you need the bench column in the output."""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

DB_DIR       = Path(__file__).resolve().parent
ANALYSIS_DIR = DB_DIR / "analysis"
DATA_DIR     = DB_DIR / "data"
DB_PATH      = DATA_DIR / "memlog.duckdb"
TMP_DIR      = DB_DIR / ".duckdb_tmp"

# 32 GB RAM, 8 GB swap, 66 GB of parquet behind `all_stores`. Without spill
# config, hash-aggregates on the bigger benches OOM-kill the process before
# DuckDB can react. Cap memory below the kernel's OOM trigger and point spill
# at the data disk (~500 GB free).
MEMORY_LIMIT = "24GB"
# Fewer threads = bigger per-thread hash-aggregate budget, which lets DuckDB
# hit the spill threshold instead of fragmenting memory across partitions.
# We're disk-bound on these queries, not CPU-bound.
THREADS      = 4


def resolve_analysis(arg: Path) -> Path:
    """Accept a folder name (e.g. '01_summary') or a path to query.sql."""
    if arg.is_file() and arg.name == "query.sql":
        return arg.resolve()
    if arg.is_dir() and (arg / "query.sql").is_file():
        return (arg / "query.sql").resolve()
    candidate = ANALYSIS_DIR / arg.name / "query.sql"
    if candidate.is_file():
        return candidate.resolve()
    raise FileNotFoundError(arg)


def list_benches(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Bench names = parquet file stems, in alphabetical order."""
    return sorted(p.stem for p in DATA_DIR.glob("*.parquet"))


def reset_tmp_dir() -> None:
    """Wipe the spill dir before each query.

    DuckDB normally cleans its own spill files when an operator finishes,
    but a kill (OOM, ctrl-C, WSL freeze) leaves orphans behind — and a
    long-running plow can otherwise accumulate hundreds of GB of stale
    spill across queries. Clearing per-query bounds disk usage to one
    query's working set."""
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def run_query(con: duckdb.DuckDBPyConnection, query_path: Path) -> Path:
    """Execute query_path's SQL and write result.csv into the same folder."""
    reset_tmp_dir()
    sql = query_path.read_text()
    out_path = query_path.parent / "result.csv"
    name     = query_path.parent.name  # analysis folder name
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
    print(f"[{name}] {len(df)} row(s) in {elapsed:.2f}s -> {out_path}")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("analysis", nargs="?", type=Path,
                    help="single analysis to run (folder name or path); "
                         "if omitted, runs every db/analysis/NN_*/query.sql "
                         "in numeric order")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"error: {DB_PATH} not found — run tools/to_parquet.py first",
              file=sys.stderr)
        return 1

    if args.analysis is not None:
        try:
            queries = [resolve_analysis(args.analysis)]
        except FileNotFoundError as e:
            print(f"error: {e} not found", file=sys.stderr)
            return 1
    else:
        queries = sorted(ANALYSIS_DIR.glob("[0-9][0-9]_*/query.sql"))
        if not queries:
            print(f"error: no NN_*/query.sql found in {ANALYSIS_DIR}",
                  file=sys.stderr)
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
                print(f"[{q.parent.name}] FAILED: {e}", file=sys.stderr)
    finally:
        con.close()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
