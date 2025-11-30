# Memlog - A Valgrind Memory Store Logger

Memlog is a Valgrind tool that logs memory stores to heap-allocated blocks. It tracks allocations above a configurable size threshold and records all write operations to those blocks, outputting the exact bit representation of stored values.

## Features

- Tracks heap allocations >= `--min-block-size` (default: 4096 bytes)
- Logs memory stores with address and value (IEEE 754 hex representation for floats)
- Records allocation and free events with stack traces
- Supports all data types: integers, floats, doubles, vectors

## Building

From the valgrind root directory:

```bash
./autogen.sh
./configure
make -j4
```

## Usage

```bash
# Basic usage
./vg-in-place --tool=memlog ./your_program

# With custom minimum block size
./vg-in-place --tool=memlog --min-block-size=8192 ./your_program

# Track smaller blocks (512 bytes and above)
./vg-in-place --tool=memlog --min-block-size=512 ./your_program
```

## Output Format

```
===ALLOC START===
Start 0x<address>, size <bytes>
   at 0x...: malloc (vg_replace_malloc.c:...)
   by 0x...: <function> (<file>:<line>)
===ALLOC END===
0x<store_address> 0x<value_hex>
0x<store_address> 0x<value_hex>
...
===FREE START===
Start 0x<address>, size <bytes>
   at 0x...: free (vg_replace_malloc.c:...)
   by 0x...: <function> (<file>:<line>)
===FREE END===
```

### Value Representation

Values are logged as their exact bit representation in hexadecimal:

| Type | Example Value | Hex Output |
|------|---------------|------------|
| float 0.6f | 0.6 | 0x3f19999a |
| float 1.5f | 1.5 | 0x3fc00000 |
| double 0.6 | 0.6 | 0x3fe3333333333333 |
| int32 | 0xDEADBEEF | 0xdeadbeef |
| int64 | -1 | 0xffffffffffffffff |

## Running Tests Manually

From the valgrind root directory:

```bash
# Run individual tests
./vg-in-place --tool=memlog --min-block-size=4096 memlog/tests/basic_alloc
./vg-in-place --tool=memlog --min-block-size=4096 memlog/tests/double_stores
./vg-in-place --tool=memlog --min-block-size=4096 memlog/tests/int_stores
./vg-in-place --tool=memlog --min-block-size=4096 memlog/tests/small_block
./vg-in-place --tool=memlog --min-block-size=4096 memlog/tests/multi_alloc
./vg-in-place --tool=memlog --min-block-size=512 memlog/tests/custom_threshold
./vg-in-place --tool=memlog --min-block-size=4096 memlog/tests/calloc_test
```

### Test Descriptions

| Test | Description |
|------|-------------|
| `basic_alloc` | Float (32-bit) stores: 0.6f, 1.5f, 42.0f, -1.0f, 3.14159f |
| `double_stores` | Double (64-bit) stores: 0.6, 1.5, 42.0, -1.0 |
| `int_stores` | 32-bit and 64-bit integer stores |
| `small_block` | Verifies blocks < threshold are NOT tracked |
| `multi_alloc` | Multiple allocations with interleaved stores |
| `custom_threshold` | Tests --min-block-size=512 option |
| `calloc_test` | Tests calloc-allocated memory tracking |

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--min-block-size=<bytes>` | 4096 | Minimum allocation size to track |

## Files

```
memlog/
├── ml_main.c           # Main tool implementation
├── ml_replace_strmem.c # Preload library for malloc interception
├── memlog.h            # Public header
├── rbtree.c            # Red-black tree for block tracking
├── rbtree.h            # RB-tree header
├── Makefile.am         # Build configuration
└── tests/              # Test suite
    ├── basic_alloc.c
    ├── double_stores.c
    ├── int_stores.c
    ├── small_block.c
    ├── multi_alloc.c
    ├── custom_threshold.c
    ├── calloc_test.c
    └── filter_stderr    # Output filter for test comparison
```

## License

This tool is part of Valgrind and is distributed under the GNU General Public License v2.
