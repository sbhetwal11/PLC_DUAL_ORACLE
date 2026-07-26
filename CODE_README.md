# PLCBench - code & benchmark (working title)

This subtree holds the **research artifacts**: the safety-property benchmark for LLM-generated IEC 61131-3 Structured Text, and the verification harness that scores generated code by **compiling it and model-checking its safety properties**.

> Project context lives in `../CLAUDE.md` and `../docs/`. This file is just how to run the code.

## Layout
```
plcbench/              # Python package (orchestration)
  schema.py            # pydantic models for a benchmark Task
  loader.py            # load + validate tasks from disk
  harness.py           # run compile + verify backends over a task
  cli.py               # command-line entry (validate / stats / check-tools / run)
  backends/
    compile_matiec.py  # ST compile backend (MATIEC) + a no-tool basic syntax checker
    verify_nuxmv.py    # formal verification backend (nuXmv) - wires in PHASE B
benchmark/
  tasks/<tier>/<TASKID>/   # one folder per task: meta.json + reference.st
  README.md            # the task/benchmark format spec
tests/                 # pytest: validates the benchmark is well-formed
toolchain/             # Dockerfile for MATIEC + nuXmv (reproducible; migrates to 5090)
requirements.txt
```

## Quick start (works on this laptop, no external tools yet)
```bash
python -m pip install -r requirements.txt          # pydantic/pytest already present
python -m plcbench.cli validate                     # validate every task against the schema
python -m plcbench.cli stats                        # benchmark size / property counts
python -m plcbench.cli check-tools                  # report which verification tools are available
python -m plcbench.cli run --task E01_motor_interlock   # run available backends on one task
pytest -q                                            # benchmark well-formedness tests
```

## Status
- **Phase A (done):** schema, benchmark tasks, harness, tests. CPU-only.
- **Phase B (implemented; pending nuXmv binary):**
 - `plcbench/st/` - ST-subset `parser`, `interp` (scan-cycle interpreter), `smv` (ST→SMV translator).
 - `backends/simulate.py` runs scenarios now; `backends/verify_nuxmv.py` runs nuXmv per property when present.
 - 12 pytest passing; reference solutions validated against scenarios; `cli smv` dumps the model.
 - **To finish Phase B:** add `toolchain/nuXmv.tar.gz` (license download) → `docker build ./toolchain` → `python -m plcbench.cli run` should show `verify=OK` for references; a buggy solution should produce a counterexample.
- **Phase C (5090):** generate code with LLMs (API + local), then fine-tune / RL with the verifier reward.

### Extra command
```bash
python -m plcbench.cli smv --task E01_motor_interlock   # dump generated SMV model
```

## Naming
Package name `plcbench` and any benchmark name are **provisional** - finalize before release.
