# Memlog

Valgrind tool that logs floating-point writes to large memory buffers.

## Quick Start

```bash
# 1. Place SPEC CPU2017 ISO in root
cp /path/to/cpu2017-1.1.9.iso .

# 2. Build
./build/install.sh

# 3. Run
docker run -it --rm memlog:latest
```

## What It Does

- Tracks memory allocations above threshold (default: 4096 bytes)
- Logs store operations to tracked blocks (address, value, offset)
- Classifies buffers as `float`, `double`, or `object`

## Project Structure

```
build/      # build scripts
examples/   # example programs
runtime/    # container scripts (analyze.sh, menu.sh)
tools/      # utilities (parser.py)
spec/       # SPEC CPU config
valgrind/   # valgrind + memlog source
```

## Troubleshooting

**Docker permission denied**: `sudo usermod -aG docker $USER` then re-login

**WSL2**: Use `/mnt/c/...` paths, ensure Docker Desktop WSL2 integration is enabled
