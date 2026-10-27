"""Compare Memlog's MX quantizer (verbatim from ml_main.c) with microxcaling.

Builds harness.c with the MX functions of ml_main.c and runs it on the same
blocks as microxcaling's _quantize_mx (fp8_e4m3, scale_bits 8, block 32,
shared_exp_method "max", round "nearest"); every element is compared bit for
bit. Pass a git revision to also check that revision's quantizer.

Usage: MICROXCALING=<checkout> python3 compare.py [git revision ...]
"""
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / "valgrind/memlog/ml_main.c"

sys.path.insert(0, os.environ["MICROXCALING"])
from mx.mx_ops import _quantize_mx  # noqa: E402
from mx.formats import ElemFormat  # noqa: E402

START = "/* IEEE layout of the stored elements"
END = "static VG_REGPARM(2) void mx_after_store"


def build(work, name, text):
    d = work / name
    d.mkdir()
    (d / "mx_region.c").write_text(text[text.index(START):text.index(END)])
    exe = d / "harness"
    subprocess.run(["gcc", "-O2", "-Wall", "-I", str(d), "-o", str(exe),
                    str(HERE / "harness.c")], check=True)
    return exe


def blocks(dtype, rng):
    """Labelled test blocks of 32 elements."""
    out = []
    big = np.float64 if dtype == np.float64 else np.float32
    lo = -1000 if dtype == np.float64 else -120
    hi = 1000 if dtype == np.float64 else 120

    def add(label, vals):
        out.append((label, np.asarray(vals, dtype=np.float64).astype(dtype)))

    def rand_vals(top, spread, n=32):
        e = rng.integers(top - spread, top + 1, n)
        m = 1 + rng.random(n)
        s = rng.choice([-1.0, 1.0], n)
        v = s * m * np.exp2(e.astype(np.float64))
        v[rng.random(n) < 0.1] = 0.0
        return v

    for spread in (0, 2, 4, 8, 12, 16, 24, 40):
        for _ in range(400):
            add(f"spread{spread}", rand_vals(int(rng.integers(lo // 10, hi // 10)), spread))
    # exact ties on the element grid, normal and below-normal parts
    for _ in range(600):
        s = int(rng.integers(-20, 20))
        v = [np.exp2(s + 8)]
        for _ in range(31):
            lead = int(rng.integers(s - 12, s + 8))
            q = max(lead, s - 6) - 3
            m = int(rng.integers(8, 16)) if lead >= s - 6 else int(rng.integers(0, 8))
            v.append(rng.choice([-1, 1]) * (m + 0.5) * np.exp2(q))
        add("ties", v)
    # largest element near the top of E4M3 (448 = 1.75 * 2^8)
    for j in range(16):
        for _ in range(40):
            s = int(rng.integers(-20, 20))
            v = rand_vals(s + 8, 6)
            v[0] = (1 + j / 16) * np.exp2(s + 8)
            add(f"top1+{j}/16", v)
    # magnitudes around the E8M0 limits
    tiny = [-119, -125, -127, -130, -135, -140] if dtype == np.float64 else [-119, -122, -126]
    for t in tiny:
        for _ in range(150):
            add(f"tiny2^{t}", rand_vals(t, 12))
    if dtype == np.float64:
        for t in (130, 134, 135, 136, 140):
            for _ in range(150):
                add(f"huge2^{t}", rand_vals(t, 12))
    # subnormal inputs
    for _ in range(300):
        v = rand_vals(int(rng.integers(lo // 10, hi // 10)), 8)
        sub = np.finfo(big).smallest_subnormal
        k = rng.integers(0, 32, 6)
        v[k] = rng.integers(1, 1000, 6) * float(sub)
        add("subnormal-mixed", v)
    for _ in range(200):
        sub = np.finfo(big).smallest_subnormal
        add("subnormal-only", rng.integers(0, 1 << 20, 32) * float(sub))
    # non-finite and zero blocks
    for special in (np.inf, -np.inf, np.nan):
        for _ in range(50):
            v = rand_vals(0, 8)
            v[int(rng.integers(0, 32))] = special
            add(f"has{special}", v)
    add("zeros", np.zeros(32))
    add("negzeros", -np.zeros(32))
    return out


def bits(a):
    return a.view(np.uint64 if a.dtype == np.float64 else np.uint32)


def same(x, y):
    """Elementwise bit equality; any NaN equals any NaN, +0 equals -0."""
    nx, ny = np.isnan(x), np.isnan(y)
    eq = (bits(x) == bits(y)) | (nx & ny) | ((x == 0) & (y == 0))
    return eq & ~(nx ^ ny)


def run(work, exe, esz, arr):
    fin, fout = work / "in.bin", work / "out.bin"
    arr.tofile(fin)
    r = subprocess.run([str(exe), str(esz), str(fin), str(fout)],
                       capture_output=True, text=True, check=True)
    return np.fromfile(fout, dtype=arr.dtype).reshape(arr.shape), r.stderr.strip()


def main():
    work = Path(tempfile.mkdtemp(prefix="mxcmp"))
    exes = [("working copy", build(work, "wc", SRC.read_text()))]
    for rev in sys.argv[1:]:
        text = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:valgrind/memlog/ml_main.c"],
                              capture_output=True, text=True, check=True).stdout
        exes.append((rev, build(work, rev, text)))
    rng = np.random.default_rng(20261027)
    failed = False

    for dtype, esz in ((np.float64, 8), (np.float32, 4)):
        data = blocks(dtype, rng)
        labels = [l for l, _ in data]
        arr = np.stack([v for _, v in data])
        ref = _quantize_mx(torch.from_numpy(arr.copy()), 8, ElemFormat.fp8_e4m3,
                           shared_exp_method="max", axes=[-1], block_size=32,
                           round="nearest").numpy()
        print(f"\n=== {np.dtype(dtype).name}: {arr.shape[0]} blocks, {arr.size} elements")
        for name, exe in exes:
            got, counters = run(work, exe, esz, arr)
            ok = same(got, ref)
            bad_blocks = Counter()
            example = defaultdict(list)
            for b in np.nonzero(~ok.all(axis=1))[0]:
                bad_blocks[labels[b]] += 1
                if len(example[labels[b]]) < 2:
                    i = int(np.nonzero(~ok[b])[0][0])
                    example[labels[b]].append((arr[b, i], got[b, i], ref[b, i]))
            nbad = int((~ok).sum())
            failed |= name == "working copy" and nbad > 0
            print(f"[{name}] {counters}")
            print(f"[{name}] elements differing from microxcaling: {nbad} "
                  f"({100 * nbad / ok.size:.3f}%), blocks: {int((~ok.all(axis=1)).sum())}")
            for lab, c in sorted(bad_blocks.items()):
                total = labels.count(lab)
                ex = "; ".join(f"x={x!r} memlog={g!r} ms={r!r}" for x, g, r in example[lab])
                print(f"    {lab:18s} {c:4d}/{total:<4d} e.g. {ex}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
