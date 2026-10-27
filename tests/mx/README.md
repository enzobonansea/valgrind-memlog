# MX emulation vs. microxcaling

Bit-for-bit checks of `--mx-round` against Microsoft's
[microxcaling](https://github.com/microsoft/microxcaling) `_quantize_mx`
(fp8_e4m3, block 32, scale_bits 8, `shared_exp_method="max"`, `round="nearest"`).
Both need `numpy`, `torch` and a microxcaling checkout.

- `compare.py`: compiles the MX functions of `ml_main.c` natively (`harness.c`)
  and runs them on ~12,000 blocks per element size, including ties, the 448
  saturation, E8M0 limits, subnormals, Inf and NaN. Extra git revisions given
  as arguments are compared too.
- `e2e.py`: runs `e2e.c` under Valgrind with `--mx-round=yes` and compares the
  selected buffer; a buffer from another site must stay untouched.

```
MICROXCALING=~/microxcaling python3 tests/mx/compare.py 3e26451
MICROXCALING=~/microxcaling VALGRIND=/opt/valgrind/inst/bin/valgrind python3 tests/mx/e2e.py
```
