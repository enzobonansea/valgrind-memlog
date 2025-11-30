#!/usr/bin/env python3
from __future__ import annotations
import bisect
import errno
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, TextIO, Tuple
from tqdm import tqdm

# ---------------- Regex ----------------
ALLOC_HEADER_RE = re.compile(r"^Start\s+0x([0-9a-fA-F]+),\s+size\s+(\d+)")
STORE_RE = re.compile(r"^0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)")

# ---------------- File handle cache (LRU) ----------------
class FileCache:
    """LRU cache for file handles to avoid too many open files."""
    def __init__(self, max_open: int = 512):
        self.max_open = max_open
        self._handles: Dict[Path, Tuple[TextIO, int]] = {}
        self._tick = 0

    def _evict_if_needed(self):
        if len(self._handles) < self.max_open:
            return
        # Evict LRU
        lru_path = min(self._handles.items(), key=lambda kv: kv[1][1])[0]
        try:
            self._handles[lru_path][0].close()
        finally:
            del self._handles[lru_path]

    def write_line(self, path: Path, line: str):
        self._tick += 1
        if path in self._handles:
            fh, _ = self._handles[path]
            self._handles[path] = (fh, self._tick)
        else:
            self._evict_if_needed()
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(path, "a", encoding="utf-8")
            self._handles[path] = (fh, self._tick)
        self._handles[path][0].write(line)

    def close_path(self, path: Path):
        h = self._handles.pop(path, None)
        if h:
            try:
                h[0].close()
            except:
                pass

    def close_all(self):
        for fh, _ in list(self._handles.values()):
            try:
                fh.close()
            except:
                pass
        self._handles.clear()

# -------------------------------------------------------
class LiveAlloc:
    """Represents a live memory allocation block between ALLOC and FREE."""
    __slots__ = (
        "start",
        "size",
        "end",
        "store_count",
        "aligned32",
        "aligned64",
        "base_core",
        "tmp_path",      # temp file of the alloc
        "usage_num",
    )

    def __init__(self, start: int, size: int, base_core: str, out_dir: Path, usage_num: int):
        self.start = start
        self.size = size
        self.end = start + size
        self.aligned32 = True
        self.aligned64 = True
        self.base_core = base_core
        self.store_count = 0
        self.usage_num = usage_num
        # Temporal per-alloc
        self.tmp_path = out_dir / f".{base_core}_{usage_num}.tmp"

    def write_store(self, addr_hex: str, value_hex: str, file_cache: FileCache) -> None:
        addr = int(addr_hex, 16)
        # sanity: bounds
        if not (self.start <= addr < self.end):
            raise ValueError(f"Store address 0x{addr_hex} out of bounds for alloc")
        offset = addr - self.start

        line = f"0x{addr_hex.lower()} 0x{value_hex.lower()} {offset}\n"
        file_cache.write_line(self.tmp_path, line)
        self.store_count += 1

        if self.aligned32 and (offset % 4 != 0):
            self.aligned32 = False
        if self.aligned64 and (offset % 8 != 0):
            self.aligned64 = False

    def close_and_finalize(self, out_dir: Path, file_cache: FileCache) -> None:
        # Close the file handle if it's cached
        file_cache.close_path(self.tmp_path)

        if self.store_count == 0:
            # No stores written, delete temp file if exists
            try:
                if self.tmp_path.exists():
                    self.tmp_path.unlink()
            except:
                pass
            return

        # Determine type based on alignment
        type_name = "object"
        if self.aligned32:
            type_name = "double" if self.aligned64 else "float"

        target = out_dir / f"{self.base_core}_{type_name}_{self.usage_num}.stores"

        # Rename atomically
        try:
            os.replace(self.tmp_path, target)
        except OSError as e:
            if e.errno == errno.EXDEV:
                # Cross-device: copy and delete
                with open(self.tmp_path, "rb") as src, open(target, "wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                try:
                    os.unlink(self.tmp_path)
                except:
                    pass
            else:
                raise

# -------------------------------------------------------
def parse_log(log_path: str | os.PathLike, max_open_files: int = 512) -> Path:
    """Parses a Valgrind memlog log file; outputs .stores files for ALLOCs that have STOREs.

    Args:
        log_path: Path to the Valgrind memlog output file
        max_open_files: Maximum number of file handles to keep open (default: 512)

    Returns:
        Path to the output directory containing .stores files
    """
    log_path = Path(log_path)
    if not log_path.is_file():
        raise FileNotFoundError(log_path)

    out_dir = log_path.with_suffix(log_path.suffix + ".parsed")
    out_dir.mkdir(exist_ok=True)

    live_allocs: Dict[int, List[LiveAlloc]] = defaultdict(list)
    starts_sorted: List[int] = []
    live_list: List[LiveAlloc] = []
    address_usage_count: Dict[int, int] = defaultdict(int)

    file_cache = FileCache(max_open=max_open_files)

    def _add(alloc: LiveAlloc):
        idx = bisect.bisect_left(starts_sorted, alloc.start)
        starts_sorted.insert(idx, alloc.start)
        live_list.insert(idx, alloc)
        live_allocs[alloc.start].append(alloc)

    def _remove(alloc: LiveAlloc):
        idx = live_list.index(alloc)
        starts_sorted.pop(idx)
        live_list.pop(idx)
        live_allocs[alloc.start].pop()

    file_size = log_path.stat().st_size
    status_log = Path("/tmp/memlog_parser_status.log")
    bytes_processed = 0
    last_log_bytes = 0
    log_interval = file_size // 100  # Log every 1% of progress

    with tqdm(total=file_size, desc="Parsing log", unit="B", unit_scale=True) as pbar, \
         log_path.open("r", encoding="utf-8", errors="ignore") as fh:

        inside_alloc = inside_free = False

        for line in fh:
            pbar.update(len(line))
            bytes_processed += len(line)

            # Log progress at intervals
            if bytes_processed - last_log_bytes >= log_interval or bytes_processed >= file_size:
                percent = (bytes_processed / file_size) * 100
                with open(status_log, "a") as log:
                    if bytes_processed >= file_size:
                        log.write(f"[{log_path.name}] Parsing completed. Files in: {out_dir}\n")
                    else:
                        log.write(f"[{log_path.name}] Parsing progress: {percent:.1f}%. Files in: {out_dir}\n")
                last_log_bytes = bytes_processed

            # STORE ------------------------------------------------------
            m_store = STORE_RE.match(line)
            if m_store:
                addr_hex, value_hex = m_store.groups()
                addr_int = int(addr_hex, 16)

                # Find the containing alloc using binary search
                pos = bisect.bisect_right(starts_sorted, addr_int) - 1
                found = False
                if pos >= 0:
                    alloc = live_list[pos]
                    if alloc.start <= addr_int < alloc.end:
                        alloc.write_store(addr_hex, value_hex, file_cache)
                        found = True

                if not found:
                    # Fallback linear search (rare case)
                    for alloc in live_list:
                        if alloc.start <= addr_int < alloc.end:
                            alloc.write_store(addr_hex, value_hex, file_cache)
                            found = True
                            break

                if not found:
                    # STORE out of any live ALLOC
                    raise ValueError(
                        f"STORE 0x{addr_hex} does not belong to any live ALLOC. "
                        f"(live={len(live_list)})."
                    )
                continue

            # ALLOC / FREE delimiters -----------------------------------
            if line.startswith("===ALLOC START==="):
                inside_alloc = True; continue
            if line.startswith("===ALLOC END==="):
                inside_alloc = False; continue
            if line.startswith("===FREE START==="):
                inside_free = True; continue
            if line.startswith("===FREE END==="):
                inside_free = False; continue

            # ALLOC header ----------------------------------------------
            if inside_alloc:
                m_alloc = ALLOC_HEADER_RE.match(line)
                if m_alloc:
                    start_hex, size_str = m_alloc.groups()
                    start_int = int(start_hex, 16)
                    size_int = int(size_str)
                    base_core = f"0x{start_hex.lower()}_{size_int}"
                    address_usage_count[start_int] += 1
                    _add(LiveAlloc(start_int, size_int, base_core, out_dir, address_usage_count[start_int]))
                continue

            # FREE header -----------------------------------------------
            if inside_free:
                m_free = ALLOC_HEADER_RE.match(line)
                if m_free:
                    start_hex, _size_str = m_free.groups()
                    start_int = int(start_hex, 16)
                    stack = live_allocs.get(start_int)
                    if stack:
                        alloc = stack[-1]
                        alloc.close_and_finalize(out_dir, file_cache)
                        _remove(alloc)
                continue

    # Finalize all live allocations that didn't get a FREE
    for alloc in list(live_list):
        alloc.close_and_finalize(out_dir, file_cache)
        _remove(alloc)

    # Close all file handles in the cache
    file_cache.close_all()

    print(f"[parse_log] Finished. Files are in: {out_dir}")
    return out_dir

# -------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Parse Valgrind memlog output files.")
    parser.add_argument("logfile", help="Path to the .log file to process")
    parser.add_argument("--max-open-files", type=int, default=512,
                        help="Maximum number of file handles to keep open (default: 512)")
    args = parser.parse_args()

    log_path = Path(args.logfile)
    if not log_path.is_file():
        print(f"[parse_log] File not found: {log_path}")
        sys.exit(1)

    out_dir = parse_log(args.logfile, max_open_files=args.max_open_files)
    sys.exit(0)
