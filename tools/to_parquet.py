#!/usr/bin/env python3
"""Convert raw/{benchmark}.tar.xz archives of parsed memlog .stores files into
db/{benchmark}.parquet.

One row per store, with allocation metadata duplicated per row (parquet
dictionary encoding makes the duplication near-free at rest).

Schema:
    alloc_addr   uint64   start address of the allocation
    alloc_size   uint64   size in bytes
    alloc_type   string   "64bits" | "32bits" | "object"
    generation   uint32   nth reuse of this start address
    alloc_stack  string   newline-joined allocation-site stack trace
    offset       uint64   byte offset of the store within the allocation
    value        uint64   value written (parsed from hex)
"""
from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
import sys
import tarfile
import threading
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

try:
    import duckdb
except ImportError:
    duckdb = None

STORE_RE = re.compile(r"^(\d+):0x([0-9a-fA-F]+)\s*$")
NAME_RE = re.compile(r"^0x([0-9a-fA-F]+)_(\d+)_(64bits|32bits|object)_(\d+)\.stores$")

TYPE_DICT = ["64bits", "32bits", "object"]
TYPE_IDX = {t: i for i, t in enumerate(TYPE_DICT)}

SCHEMA = pa.schema([
    ("alloc_addr",  pa.uint64()),
    ("alloc_size",  pa.uint64()),
    ("alloc_type",  pa.dictionary(pa.int8(), pa.string())),
    ("generation",  pa.uint32()),
    ("alloc_stack", pa.dictionary(pa.int32(), pa.large_string())),
    ("offset",      pa.uint64()),
    ("value",       pa.uint64()),
])

BATCH_ROWS = 1 << 20


class _CountingReader(io.RawIOBase):
    """Wraps a binary file object so every byte read fires a callback —
    used to drive a tqdm bar off the *compressed* tar.xz stream (no need to
    know the decompressed size ahead of time)."""

    def __init__(self, fh, on_read):
        self._fh = fh
        self._on_read = on_read

    def readable(self) -> bool:
        return True

    def read(self, n=-1):
        chunk = self._fh.read(n)
        if chunk:
            self._on_read(len(chunk))
        return chunk

    def readinto(self, buf):
        n = self._fh.readinto(buf)
        if n:
            self._on_read(n)
        return n

    def close(self):
        try:
            self._fh.close()
        finally:
            super().close()


def _read_stack_header(fh) -> tuple[list[str], bytes | None]:
    """Read leading '# ...' stack lines from a .stores stream. Returns the
    collected stack lines and the first non-header line (or None on EOF) so
    the caller can resume parsing the body without re-reading."""
    stack_lines: list[str] = []
    for raw in fh:
        if not raw:
            continue
        if raw[:1] == b"#":
            stack_lines.append(raw[1:].decode("utf-8", errors="ignore").strip())
            continue
        return stack_lines, raw
    return stack_lines, None


def _open_tar_stream(archive: Path, on_compressed_byte, use_pixz: bool):
    """Return (tar_fileobj, mode, cleanup) for streaming through `archive`.

    When pixz is available it's used for parallel xz decompression; the feeder
    thread reads the compressed file and reports bytes read to `on_compressed_byte`.
    Otherwise we fall back to Python's single-threaded lzma via tarfile's 'r|xz'
    mode, with a wrapper that reports bytes from the same compressed stream.
    """
    if use_pixz:
        proc = subprocess.Popen(
            ["pixz", "-d"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        feeder_err: list[BaseException] = []

        def feeder():
            try:
                with archive.open("rb") as raw:
                    while True:
                        chunk = raw.read(1 << 20)
                        if not chunk:
                            break
                        proc.stdin.write(chunk)
                        on_compressed_byte(len(chunk))
            except BaseException as e:
                feeder_err.append(e)
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass

        t = threading.Thread(target=feeder, daemon=True)
        t.start()

        def cleanup():
            t.join(timeout=5.0)
            try:
                rc = proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                rc = proc.wait()
            stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
            try:
                proc.stderr.close()
            except Exception:
                pass
            if feeder_err:
                raise feeder_err[0]
            if rc != 0:
                raise RuntimeError(f"pixz -d exited {rc}: {stderr.strip()}")

        # tarfile reads an uncompressed tar from pixz stdout
        return proc.stdout, "r|", cleanup

    # Fallback: Python lzma via tarfile, byte counter on the compressed stream
    raw_fh = archive.open("rb")
    wrapped = _CountingReader(raw_fh, on_compressed_byte)

    def cleanup():
        try:
            raw_fh.close()
        except Exception:
            pass

    return wrapped, "r|xz", cleanup


def convert_archive(archive: Path, out_path: Path,
                    use_pixz: bool = False) -> tuple[int, int]:
    """Stream a tar.xz of .stores files directly into a parquet, with a
    progress bar tracking compressed bytes read. No temp directory — works
    for archives larger than available disk."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Per-row buffers store *indices* into the dictionaries below, not the
    # strings themselves. This keeps Python-side memory bounded by the number
    # of unique allocations rather than the total store count, and avoids
    # tripping pa.array's 2 GiB single-chunk cap on string columns.
    buf_alloc_addr: list[int] = []
    buf_alloc_size: list[int] = []
    buf_type_idx:   list[int] = []
    buf_generation: list[int] = []
    buf_stack_idx:  list[int] = []
    buf_offset:     list[int] = []
    buf_value:      list[int] = []

    type_dict_arr = pa.array(TYPE_DICT, type=pa.string())
    stack_dict_strs: list[str] = []
    stack_idx_of: dict[str, int] = {}

    n_alloc = 0
    n_stores = 0
    skipped = 0
    writer: pq.ParquetWriter | None = None

    def flush():
        nonlocal writer
        if not buf_offset:
            return
        stack_dict_arr = pa.array(stack_dict_strs, type=pa.large_string())
        table = pa.table(
            {
                "alloc_addr":  pa.array(buf_alloc_addr, type=pa.uint64()),
                "alloc_size":  pa.array(buf_alloc_size, type=pa.uint64()),
                "alloc_type":  pa.DictionaryArray.from_arrays(
                    pa.array(buf_type_idx, type=pa.int8()), type_dict_arr),
                "generation":  pa.array(buf_generation, type=pa.uint32()),
                "alloc_stack": pa.DictionaryArray.from_arrays(
                    pa.array(buf_stack_idx, type=pa.int32()), stack_dict_arr),
                "offset":      pa.array(buf_offset, type=pa.uint64()),
                "value":       pa.array(buf_value,  type=pa.uint64()),
            },
            schema=SCHEMA,
        )
        if writer is None:
            writer = pq.ParquetWriter(out_path, SCHEMA, compression="zstd")
        writer.write_table(table)
        buf_alloc_addr.clear()
        buf_alloc_size.clear()
        buf_type_idx.clear()
        buf_generation.clear()
        buf_stack_idx.clear()
        buf_offset.clear()
        buf_value.clear()

    total = archive.stat().st_size
    desc = f"{archive.name} ({'pixz' if use_pixz else 'lzma'})"
    with tqdm(total=total, unit="B", unit_scale=True, unit_divisor=1024,
              desc=desc, smoothing=0.05) as pbar:
        tar_fh, mode, cleanup = _open_tar_stream(archive, pbar.update, use_pixz)
        try:
            with tarfile.open(fileobj=tar_fh, mode=mode) as tf:
                for member in tf:
                    if not member.isfile():
                        continue
                    base = Path(member.name).name
                    if not base.endswith(".stores"):
                        continue
                    m = NAME_RE.match(base)
                    if not m:
                        skipped += 1
                        continue
                    addr = int(m.group(1), 16)
                    size = int(m.group(2))
                    type_name = m.group(3)
                    generation = int(m.group(4))

                    fh = tf.extractfile(member)
                    if fh is None:
                        continue

                    # Stream the body line-by-line so a single huge
                    # allocation can't grow the column buffers past
                    # BATCH_ROWS. Stack lines all come first; the one
                    # non-header line that signals body-start is returned
                    # by _read_stack_header so we don't lose it.
                    stack_lines, first_body = _read_stack_header(fh)
                    stack_str = "\n".join(stack_lines)
                    sidx_for_alloc = -1   # resolved on first store
                    t_idx = TYPE_IDX[type_name]
                    n_in_alloc = 0

                    def consume_line(raw: bytes):
                        nonlocal sidx_for_alloc, n_in_alloc, n_stores
                        line = raw.decode("utf-8", errors="ignore")
                        sm = STORE_RE.match(line)
                        if not sm:
                            return
                        if sidx_for_alloc < 0:
                            sidx = stack_idx_of.get(stack_str)
                            if sidx is None:
                                sidx = len(stack_dict_strs)
                                stack_dict_strs.append(stack_str)
                                stack_idx_of[stack_str] = sidx
                            sidx_for_alloc = sidx
                        buf_alloc_addr.append(addr)
                        buf_alloc_size.append(size)
                        buf_type_idx.append(t_idx)
                        buf_generation.append(generation)
                        buf_stack_idx.append(sidx_for_alloc)
                        buf_offset.append(int(sm.group(1)))
                        buf_value.append(int(sm.group(2), 16))
                        n_in_alloc += 1
                        n_stores += 1
                        if len(buf_offset) >= BATCH_ROWS:
                            flush()

                    if first_body is not None:
                        consume_line(first_body)
                    for raw in fh:
                        consume_line(raw)

                    if n_in_alloc == 0:
                        continue
                    n_alloc += 1
                    if n_alloc % 64 == 0:
                        pbar.set_postfix(allocs=n_alloc, stores=n_stores,
                                         refresh=False)
        finally:
            cleanup()

    flush()
    if writer is None:
        # No stores found; emit an empty parquet with the schema so the file exists.
        writer = pq.ParquetWriter(out_path, SCHEMA, compression="zstd")
    writer.close()

    if skipped:
        print(f"  ({skipped} member(s) skipped: unrecognized .stores name)",
              file=sys.stderr)
    return n_alloc, n_stores


VIEW_NAME_RE = re.compile(r"[^A-Za-z0-9_]")


def view_name_for(parquet_path: Path) -> str:
    name = VIEW_NAME_RE.sub("_", parquet_path.stem)
    if name and name[0].isdigit():
        name = "_" + name
    return name


def refresh_duckdb(db_path: Path, db_dir: Path) -> None:
    """(Re)create a view per *.parquet in db_dir inside db_path. Idempotent —
    drops any existing view of the same name first so view definitions track
    the current parquet set."""
    if duckdb is None:
        print("duckdb not installed; skipping view refresh "
              "(pip install --user duckdb)", file=sys.stderr)
        return

    parquets = sorted(db_dir.glob("*.parquet"))
    con = duckdb.connect(str(db_path))
    try:
        for pq_path in parquets:
            view = view_name_for(pq_path)
            abs_path = str(pq_path.resolve()).replace("'", "''")
            # `rn` exposes parquet's physical row position so window queries
            # (silent stores, snapshot last-write) can ORDER BY a real column
            # instead of `ROW_NUMBER() OVER ()`, whose global sort blows
            # DuckDB's spill budget on the larger benches.
            con.execute(f'CREATE OR REPLACE VIEW "{view}" '
                        f"AS SELECT *, file_row_number AS rn "
                        f"FROM read_parquet('{abs_path}', file_row_number=true)")
        if parquets:
            union_sql = " UNION ALL ".join(
                f"SELECT '{view_name_for(p)}' AS bench, * FROM \"{view_name_for(p)}\""
                for p in parquets
            )
            con.execute(f'CREATE OR REPLACE VIEW "all_stores" AS {union_sql}')
        else:
            con.execute('DROP VIEW IF EXISTS "all_stores"')
        con.execute("CHECKPOINT")
    finally:
        con.close()
    size_kib = db_path.stat().st_size / 1024
    print(f"[duckdb] {db_path} refreshed: {len(parquets)} per-bench view(s) "
          f"+ all_stores ({size_kib:.1f} KiB)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", default="raw", type=Path,
                    help="directory of *.tar.xz archives (default: raw)")
    ap.add_argument("--db-dir", default="db", type=Path,
                    help="output directory for *.parquet (default: db)")
    ap.add_argument("--duckdb", default="db/memlog.duckdb", type=Path,
                    help="DuckDB file to refresh with one view per parquet "
                         "(default: db/memlog.duckdb; set to '' to skip)")
    ap.add_argument("--no-pixz", action="store_true",
                    help="disable pixz parallel xz decompression even if "
                         "available (default: auto-detect)")
    ap.add_argument("--force", action="store_true",
                    help="re-convert archives even if a newer parquet exists "
                         "(default: skip up-to-date archives)")
    ap.add_argument("archives", nargs="*", type=Path,
                    help="optional explicit archive paths; default: all *.tar.xz under --raw-dir")
    args = ap.parse_args()

    use_pixz = (not args.no_pixz) and shutil.which("pixz") is not None
    if not use_pixz and not args.no_pixz and shutil.which("pixz") is None:
        print("note: pixz not found; using single-threaded Python lzma. "
              "For 100GB+ archives install with `sudo apt install pixz`.",
              file=sys.stderr)

    archives = args.archives or sorted(args.raw_dir.glob("*.tar.xz"))
    if not archives:
        print(f"no archives found in {args.raw_dir}", file=sys.stderr)
        return 1

    args.db_dir.mkdir(parents=True, exist_ok=True)
    for arc in archives:
        name = arc.name
        if name.endswith(".tar.xz"):
            stem = name[:-len(".tar.xz")]
        else:
            stem = arc.stem
        out = args.db_dir / f"{stem}.parquet"

        if (not args.force
                and out.exists()
                and out.stat().st_mtime >= arc.stat().st_mtime):
            size_mb = out.stat().st_size / (1024 * 1024)
            print(f"[{name}] up-to-date, skipping ({out}, {size_mb:.2f} MiB) "
                  f"-- pass --force to reconvert")
            continue

        n_alloc, n_stores = convert_archive(arc, out, use_pixz=use_pixz)
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"[{name}] {n_alloc} allocations, {n_stores} stores -> "
              f"{out} ({size_mb:.2f} MiB)")

    if str(args.duckdb):
        refresh_duckdb(args.duckdb, args.db_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
