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
WATCH_SWAP_GB  = 15.5  # max swap used (out of 16 GB); Q09/Q21 spill management needs headroom
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
             spill_limit: float = WATCH_SPILL_GB) -> None:
    """Interrupt the running query if disk/spill/swap cross safety thresholds.
    Runs in a daemon thread; self-exits when `stop` is set."""
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
                  flush=True)
            last_progress = elapsed


def run_query(con: duckdb.DuckDBPyConnection, query_path: Path) -> Path:
    """Execute query_path's SQL and write result.csv into the same folder."""
    reset_tmp_dir()
    sql       = query_path.read_text()
    out_path  = query_path.parent / "result.csv"
    done_path = query_path.parent / "result.complete"
    name      = query_path.parent.name
    t0        = time.perf_counter()

    if done_path.exists():
        print(f"[{name}] already complete — skipping")
        return out_path

    directives   = _parse_directives(sql)
    threads      = int(directives.get("threads", THREADS))
    memory_limit = directives.get("memory_limit", MEMORY_LIMIT)
    spill_limit  = float(directives.get("watch_spill_gb", WATCH_SPILL_GB))

    if threads != THREADS:
        con.execute(f"PRAGMA threads={threads}")
    if memory_limit != MEMORY_LIMIT:
        con.execute(f"PRAGMA memory_limit='{memory_limit}'")

    stop = threading.Event()
    wd   = threading.Thread(target=watchdog, args=(con, stop, name, t0, spill_limit),
                             daemon=True)
    wd.start()
    try:
        if "{bench}" in sql:
            benches = list_benches(con)

            # Detect completed benches from a prior partial run
            completed: set[str] = set()
            if out_path.exists():
                try:
                    prev = pd.read_csv(out_path)
                    if "bench" in prev.columns:
                        completed = set(prev["bench"].unique())
                except Exception:
                    pass

            todo = [b for b in benches if b not in completed]
            if completed:
                print(f"[{name}] resuming: {len(completed)}/{len(benches)} benches done, "
                      f"{len(todo)} remaining", flush=True)

            if todo:
                write_header = not out_path.exists() or not completed
                for bench in todo:
                    overall_i     = benches.index(bench) + 1
                    bench_t0      = time.perf_counter()
                    total_elapsed = bench_t0 - t0
                    # `replace` instead of `format` — SQL comments may legitimately
                    # contain `{...}` text (e.g. set-builder notation in docs)
                    # that str.format would misinterpret as a placeholder.
                    print(f"  [{name}] [{overall_i}/{len(benches)}] starting {bench} "
                          f"(total elapsed: {total_elapsed:.0f}s)...",
                          flush=True)
                    result_df     = con.execute(sql.replace("{bench}", bench)).fetchdf()
                    bench_elapsed = time.perf_counter() - bench_t0
                    spill_gb      = _spill_size_gb()
                    total_elapsed = time.perf_counter() - t0
                    print(f"  [{name}] [{overall_i}/{len(benches)}] {bench}: "
                          f"{len(result_df)} rows in {bench_elapsed:.1f}s "
                          f"(spill: {spill_gb:.1f}GB, total: {total_elapsed:.0f}s)",
                          flush=True)
                    result_df.to_csv(out_path,
                                     mode='w' if write_header else 'a',
                                     header=write_header, index=False)
                    write_header = False

            n_rows = sum(1 for _ in out_path.open()) - 1 if out_path.exists() else 0
        else:
            df = con.execute(sql).fetchdf()
            df.to_csv(out_path, index=False)
            n_rows = len(df)
    finally:
        stop.set()
        wd.join(timeout=WATCH_POLL_S * 2)
        if threads != THREADS:
            con.execute(f"PRAGMA threads={THREADS}")
        if memory_limit != MEMORY_LIMIT:
            con.execute(f"PRAGMA memory_limit='{MEMORY_LIMIT}'")

    done_path.touch()
    elapsed = time.perf_counter() - t0
    print(f"[{name}] {n_rows} row(s) in {elapsed:.2f}s -> {out_path}")
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

    # One-time migration: stamp result.complete for non-bench analyses that were
    # completed before this sentinel was introduced.
    for q in ANALYSIS_DIR.glob("[0-9][0-9]_*/query.sql"):
        csv = q.parent / "result.csv"
        sentinel = q.parent / "result.complete"
        if csv.exists() and not sentinel.exists() and "{bench}" not in q.read_text():
            sentinel.touch()

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
