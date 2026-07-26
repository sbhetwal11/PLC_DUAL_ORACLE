# Verification toolchain (Phase B)

Builds a reproducible image with **MATIEC** (`iec2c`, ST→C compiler) and **nuXmv**
(model checker). Same image works on this laptop and the Vast.ai 5090 box.

## One manual step: nuXmv license
nuXmv can't be auto-downloaded (license click-through). Download the **Linux 64-bit**
build from <https://nuxmv.fbk.eu/> and save it here as `toolchain/nuXmv.tar.xz`
(v2.2.0 used here; layout `nuXmv-2.2.0-linux64/usr/local/bin/nuXmv`). This file is
git-ignored (license + 23 MB) - re-download per machine. NuSMV is a fully-open
alternative if preferred.

## Fastest path used so far: WSL (no Docker needed)
This machine has WSL Ubuntu, and the verification was first run there:
```powershell
bash toolchain/wsl_run.sh      # from the repo root; scripts derive their own path
```
`wsl_verify.sh` extracts + sanity-checks nuXmv; `wsl_run.sh` makes a venv, installs
pydantic, sets `NUXMV_BIN`, and runs the harness end-to-end (references verify true;
a buggy solution yields a counterexample). On the 5090 box, Docker (below) is the
reproducible equivalent.

## Build & run
```bash
# from the repo root (PLCCodeGenResearch/)
docker build -t plcbench-tc ./toolchain
docker run --rm -it -v "$PWD":/work -w /work plcbench-tc bash
# inside the container:
python3 -m plcbench.cli check-tools     # expect: MATIEC available, nuXmv available
python3 -m plcbench.cli run             # compiles the reference solutions
pytest -q
```

## Without Docker (WSL Ubuntu alternative)
This machine has WSL Ubuntu. You can instead:
```bash
wsl
sudo apt-get update && sudo apt-get install -y build-essential flex bison autoconf automake libtool git python3 python3-pip
# build MATIEC as in the Dockerfile, install nuXmv binary on PATH, then run the CLI.
```

## What Phase B wires up next (in `plcbench/backends/`)
1. `compile_matiec.py` - already calls `iec2c` when present (detects `MATIEC_IEC2C`/PATH).
2. `verify_nuxmv.py` - to implement: translate ST → model-checkable form (PLCverif-style
   ST→SMV, or a focused translator for the benchmark's bounded interfaces), run nuXmv per
   property, parse PASS/FAIL + **counterexamples** (the Phase-C repair/reward signal).

## Status
- **nuXmv verification: WORKING** (via `wsl_run.sh`; all 18 references verify).
- **Phase C eval: WORKING** - `wsl_eval.sh [model]` runs `eval-llm` with nuXmv. The
  `reference` model scores verified_rate = 1.0 (pipeline sanity).
- **MATIEC compile-check: deferred locally.** Building it needs `flex bison autoconf
  automake` via `sudo apt`, which requires a password (not available non-interactively
  here; gcc/make/git are present). To enable it:
 - **Interactive WSL:** `wsl` → `sudo apt-get install -y flex bison autoconf automake`
    → `bash toolchain/wsl_build_matiec.sh` (sets `MATIEC_IEC2C`), or
 - **Docker (5090):** `docker build -t plcbench-tc ./toolchain` builds it as root (no
    prompt). The compile-check is a *secondary* signal; nuXmv verification is the headline.

## Running an LLM baseline (Phase C)
With nuXmv set up (and an API key exported), in WSL:
```bash
export ANTHROPIC_API_KEY=...      # or OPENAI_API_KEY=...
bash toolchain/wsl_eval.sh anthropic:claude-3-5-sonnet-latest
bash toolchain/wsl_eval.sh openai:gpt-4o
```
Results (verified rate, compile rate, property/scenario pass, by tier) print and are
written to `results/<model>.json` (git-ignored).
