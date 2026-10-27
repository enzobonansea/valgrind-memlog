"""Run e2e.c under Memlog with --mx-round and compare the MX buffer with
microxcaling bit for bit. Blocks cover ordinary spreads, a largest element
in the saturating top binade, clamped scales, a NaN block and a scale above
E8M0; the staging buffer, not an MX site, must stay untouched.

Usage: MICROXCALING=<checkout> [VALGRIND=<valgrind binary>] python3 e2e.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
VG = os.environ.get("VALGRIND", "/opt/valgrind/inst/bin/valgrind")
sys.path.insert(0, os.environ["MICROXCALING"])
from mx.mx_ops import _quantize_mx  # noqa: E402
from mx.formats import ElemFormat  # noqa: E402

rng = np.random.default_rng(7)
blocks = []
for _ in range(2048):
    s = int(rng.integers(-60, 60))
    spread = int(rng.integers(1, 20))
    e = rng.integers(s + 8 - spread, s + 8, 32)          # below the top binade
    v = rng.choice([-1.0, 1.0], 32) * (1 + rng.random(32)) * np.exp2(e.astype(float))
    v[rng.random(32) < 0.1] = 0.0
    v[0] = rng.choice([1.0, 1.25, 1.5, 1.75]) * np.exp2(s + 8)   # exact max
    blocks.append(v)
for _ in range(512):                                       # saturating top binade
    s = int(rng.integers(-60, 60))
    e = rng.integers(s, s + 9, 32)
    v = rng.choice([-1.0, 1.0], 32) * (1 + rng.random(32)) * np.exp2(e.astype(float))
    v[0] = (1.75 + 0.25 * rng.random()) * np.exp2(s + 8)
    blocks.append(v)
for t in (-125, -130, -140):                               # clamped scales
    blocks.append(rng.random(32) * np.exp2(t))
blocks.append(np.full(32, 1.0))
blocks[-1][3] = np.nan                                     # NaN block
blocks.append(np.full(32, 1.0) * np.exp2(140))             # scale above E8M0
arr = np.stack(blocks)

work = Path(tempfile.mkdtemp(prefix="mxe2e"))
fin, fout, exe, sites = work / "in.bin", work / "out.bin", work / "e2e", work / "sites.txt"
arr.tofile(fin)
sites.write_text("mx_target_alloc\n")
subprocess.run(["gcc", "-O1", "-g", "-o", str(exe), str(HERE / "e2e.c"), "-lm"], check=True)
r = subprocess.run([VG, "--tool=memlog", "--mx-round=yes", f"--mx-sites-file={sites}",
                    str(exe), str(fin), str(fout)], capture_output=True, text=True)
print("exit", r.returncode)
print("\n".join(l for l in r.stderr.splitlines() if "MX:" in l or "rror" in l))

raw = np.fromfile(fout, dtype=np.float64)
got, staging = raw[:arr.size].reshape(arr.shape), raw[arr.size:].reshape(arr.shape)
ref = _quantize_mx(torch.from_numpy(arr.copy()), 8, ElemFormat.fp8_e4m3,
                   shared_exp_method="max", axes=[-1], block_size=32,
                   round="nearest").numpy()


def same(x, y):
    nx, ny = np.isnan(x), np.isnan(y)
    return ((x.view(np.uint64) == y.view(np.uint64)) | (nx & ny)
            | ((x == 0) & (y == 0))) & ~(nx ^ ny)


untouched = bool(same(staging, arr).all())
bad = ~same(got, ref)
print("staging buffer untouched:", untouched)
print("MX buffer changed elements:", int((~same(got, arr)).sum()), "of", arr.size)
print("elements differing from microxcaling:", int(bad.sum()))
for b, i in list(zip(*np.nonzero(bad)))[:5]:
    print("  block", b, "elem", i, arr[b, i], got[b, i], ref[b, i])
sys.exit(0 if r.returncode == 0 and untouched and not bad.any() else 1)
