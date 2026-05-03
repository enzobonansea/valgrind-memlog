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
import re
import shutil
import sys
import threading
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
MEMORY_LIMIT = "16GB"
# Threads: 4 is the sweet spot. Window-heavy queries (Q09/Q10/Q14/Q19/Q20/
# Q21/Q22/Q28/Q31) get watchdog'd at high thread counts because per-thread
# sort buffers + buffer pool exceed memory_limit and the OS reaches for
# swap. CPU-bound queries (Q13 — bit_count/xor/regex over billions of
# stores) NEED more threads or they take hours single-threaded. The
# watchdog catches the bad case; the speedup pays for everything else.
THREADS      = 4

# Watchdog limits — interrupt the running query before WSL freezes the host.
# Q09 in its previous incarnation spilled 147 GB and ate the host VHDX; these
# numbers are well inside that ceiling.
WATCH_SPILL_GB = 100   # max .duckdb_tmp size
WATCH_FREE_GB  = 30    # min free disk on /
WATCH_SWAP_GB  = 7.8   # max swap used (out of 8 GB); Q09/Q21 spill management needs headroom
WATCH_TIME_S   = 3600  # max wall time per query — kill and retry later
WATCH_POLL_S   = 5

_SET_RE = re.compile(r"^--\s*@set\s+(\w+)\s+(.+?)\s*$", re.MULTILINE)


def _parse_directives(sql: str) -> dict:
    """Parse -- @set <key> <value> directives from SQL comments."""
    return {m.group(1): m.group(2).strip() for m in _SET_RE.finditer(sql)}


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


def _swap_used_gb() -> float:
    try:
        with open("/proc/meminfo") as f:
            kv = dict(line.split(":", 1) for line in f if ":" in line)
        total = int(kv["SwapTotal"].strip().split()[0])
        free  = int(kv["SwapFree"].strip().split()[0])
        return (total - free) / 1024 / 1024
    except Exception:
        return 0.0


def _spill_size_gb() -> float:
    total = 0
    try:
        for f in TMP_DIR.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        return 0.0
    return total / 1024**3


def watchdog(con: duckdb.DuckDBPyConnection,
             stop: threading.Event,
             query_name: str,
             t0: float,
             spill_limit: float = WATCH_SPILL_GB,
             time_limit: float = WATCH_TIME_S) -> None:
    """Interrupt the running query if disk/spill/swap cross safety thresholds
    or wall time exceeds time_limit. Runs in a daemon thread; self-exits
    when `stop` is set."""
    last_progress = t0
    while not stop.wait(WATCH_POLL_S):
        spill_gb = _spill_size_gb()
        free_gb  = shutil.disk_usage(DB_DIR).free / 1024**3
        swap_gb  = _swap_used_gb()
        elapsed  = time.perf_counter() - t0
        reason = None
        if spill_gb > spill_limit: reason = "spill"
        elif free_gb < WATCH_FREE_GB: reason = "disk"
        elif swap_gb > WATCH_SWAP_GB: reason = "swap"
        elif elapsed > time_limit:  reason = "time"
        if reason:
            print(f"[{query_name}] watchdog ({reason}): "
                  f"spill={spill_gb:.1f}GB free={free_gb:.1f}GB "
                  f"swap={swap_gb:.1f}GB elapsed={elapsed:.0f}s — INTERRUPTING",
                  file=sys.stderr, flush=True)
            try:
                con.interrupt()
            except Exception:
                pass
            return
        # Print progress every 10 seconds
        if elapsed - last_progress >= 10:
            pct_spill = 100.0 * spill_gb / spill_limit if spill_limit > 0 else 0
            print(f"  [{query_name}] {elapsed:.0f}s | spill: {spill_gb:.1f}/{spill_limit:.0f}GB ({pct_spill:.0f}%) | "
                  f"free: {free_gb:.0f}GB",
                  file=sys.stderr, flush=True)
            last_progress = elapsed


def run_query(con: duckdb.DuckDBPyConnection, query_path: Path) -> Path:
    """Execute query_path's SQL and write result.csv into the same folder."""
    reset_tmp_dir()
    sql = query_path.read_text()
    out_path = query_path.parent / "result.csv"
    name     = query_path.parent.name  # analysis folder name
    t0 = time.perf_counter()

    # Parse per-query directives
    directives = _parse_directives(sql)
    threads = int(directives.get("threads", THREADS))
    memory_limit = directives.get("memory_limit", MEMORY_LIMIT)
    spill_limit = float(directives.get("watch_spill_gb", WATCH_SPILL_GB))
    time_limit = float(directives.get("watch_time_s", WATCH_TIME_S))

    # Apply per-query overrides
    if threads != THREADS:
        con.execute(f"PRAGMA threads={threads}")
    if memory_limit != MEMORY_LIMIT:
        con.execute(f"PRAGMA memory_limit='{memory_limit}'")

    stop = threading.Event()
    wd   = threading.Thread(target=watchdog, args=(con, stop, name, t0, spill_limit, time_limit),
                             daemon=True)
    wd.start()
    try:
        if "{bench}" in sql:
            frames: list[pd.DataFrame] = []
            benches = list_benches(con)
            for i, bench in enumerate(benches, 1):
                # `replace` instead of `format` — SQL comments may legitimately
                # contain `{...}` text (e.g. set-builder notation in docs)
                # that str.format would misinterpret as a placeholder.
                bench_t0 = time.perf_counter()
                total_elapsed = bench_t0 - t0
                print(f"  [{name}] [{i}/{len(benches)}] starting {bench} (total elapsed: {total_elapsed:.0f}s)...",
                      file=sys.stderr, flush=True)
                result_df = con.execute(sql.replace("{bench}", bench)).fetchdf()
                frames.append(result_df)
                bench_elapsed = time.perf_counter() - bench_t0
                spill_gb = _spill_size_gb()
                total_elapsed = time.perf_counter() - t0
                print(f"  [{name}] [{i}/{len(benches)}] {bench}: {len(result_df)} rows in {bench_elapsed:.1f}s (spill: {spill_gb:.1f}GB, total: {total_elapsed:.0f}s)",
                      file=sys.stderr, flush=True)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        else:
            df = con.execute(sql).fetchdf()
    finally:
        stop.set()
        wd.join(timeout=WATCH_POLL_S * 2)
        # Restore defaults
        if threads != THREADS:
            con.execute(f"PRAGMA threads={THREADS}")
        if memory_limit != MEMORY_LIMIT:
            con.execute(f"PRAGMA memory_limit='{MEMORY_LIMIT}'")

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
