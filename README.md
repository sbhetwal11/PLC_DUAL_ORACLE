# PLC Dual-Oracle: benchmark, harness, and verifier-grounded training for IEC 61131-3 Structured Text

This repository is the artifact for the paper *"Evaluating and Training IEC 61131-3
Structured Text Generators with Compiler, Invariant, and Scenario Feedback"* (under
review). It contains the 22-task safety-property benchmark, the full evaluation
harness (compiler + model checker + scenario interpreter), the training and reward
code, the released LoRA adapters, and the raw results behind every number in the
paper.

A generated program counts as **all-checks-pass** ("task-valid") only if it

1. compiles under a real IEC 61131-3 front end (MATIEC `iec2c`),
2. satisfies every formal safety invariant (nuXmv, via a scan-indexed ST-to-SMV
   translation included and differentially tested here), and
3. reproduces all reference execution scenarios in a scan-cycle interpreter.

## Headline results (July 2026 panel, n=10 per task, 22 tasks)

Compile-and-invariant pass@1 / pass@10:

| Model | pass@1 | pass@10 |
|---|---|---|
| grok-4.3 (retired `grok-3` slug, `reasoning_effort=none`) | 0.677 | 0.909 |
| claude-sonnet-4-6 | 0.555 | 0.636 |
| gpt-4o | 0.109 | 0.409 |
| gemini-2.5-flash | 0.100 | 0.273 |

Two findings shape the metric. First, property checking without a compilation
requirement overestimates the compile-and-invariant rate by up to 0.186 absolute
pass@1 (2.71x, gpt-4o; every completion behind this number is in
`results/frontier_n10/` and the recompute is `results/rq2_july.json`). Second, an
inert all-outputs-FALSE controller is compile-and-invariant on 20 of 22 tasks but
all-checks-pass on none, which is why execution scenarios are part of both the metric
and the RL reward.

Training (Qwen2.5-Coder, QLoRA): procedural-domain SFT is the largest single
intervention (all-checks-pass pass@1 0.045 to 0.362); a functional-reward GRPO run
lifts its warm start from 0.179 to 0.282 at a single oracle call; a
critical-property-gated reward variant adds a small, seed-consistent
compile-and-invariant gain (paired +0.029). All training comparisons are exploratory
and development-set bound; see the paper for the full caveat set.

## Repository layout

```
benchmark/tasks/        22 tasks (7 easy / 11 medium / 4 hard), 71 safety
                        properties, 48 scenarios; meta.json + reference.st each
plcbench/               harness: ST parser, scan-cycle interpreter, ST->SMV
                        translator, MATIEC/nuXmv backends, scoring CLI
analysis/               every analysis script used in the paper (RQ2 recompute,
                        bootstraps, mutation battery, differential tests, audits)
finetune/               SFT/GRPO training code, reward functions (unit-tested),
                        SFT corpora, RL prompt sets
finetune/out/           released LoRA adapters: sftlite_s{0,1,2} and the
                        gated-reward runs (rlgated_sftlite_s{0,1,2})
results/                raw per-seed and per-sample outputs behind every table:
                        frontier panels (program text retained for all 880+880
                        samples), training evals, differential tests, audits
toolchain/              build and run scripts; pinned MATIEC source tarball
                        (SHA-256 in the paper); nuXmv is downloaded separately
docs/                   experimental records (baselines, training, task-valid
                        re-scoring, gated run, external-set freeze, errata)
docs/review_package/    rubric-based expert-review package (10 dimensions,
                        22 task sheets, agreement tooling)
external_testset_draft/ frozen 12-task family-disjoint external test set (v1.0,
                        SHA-256 manifest; single-shot confirmatory protocol)
```

## Reproducing the evaluation

The harness runs on plain CPU Linux (or WSL). You need two external tools:

1. **MATIEC** (`iec2c`): build from `toolchain/matiec_src.tar.gz` (the exact pinned
   snapshot; GPL). Expected install path: `~/matiec/iec2c` with the standard library
   at `~/matiec/lib`.
2. **nuXmv 2.2.0**: download from https://nuxmv.fbk.eu (academic/non-commercial
   license; not redistributable, so it is not in this repo). Expected path:
   `~/nuxmv/.../nuXmv`.

Then:

```bash
pip install -e .
python -m plcbench.cli check-tools          # both oracles must report available
python -m plcbench.cli eval-reference       # 22/22 references compile and verify
bash toolchain/wsl_analysis.sh analysis/rq2_july.py   # re-derive the RQ2 numbers
```

Every table in the paper can be recomputed from `results/` with the scripts in
`analysis/` (the mapping is listed in the supplementary material's reproducibility
checklist). Scoring a stored completion needs only `plcbench.harness.evaluate`.

## The external test set

`external_testset_draft/` holds a 12-task, family-disjoint test set (X01-X12, 67
properties) that was expert-reviewed, corrected, and frozen (v1.0,
`FREEZE_MANIFEST.sha256`). Per its lock protocol it has never been used for any
development decision and each system may be evaluated on it exactly once. If you use
it, report single-shot numbers and do not tune against it.

## License

Code and benchmark: MIT (see `LICENSE`). MATIEC is GPL (pinned source tarball
included). nuXmv is separately licensed for academic/non-commercial use and must be
obtained from its authors. Model adapters are derived from Qwen2.5-Coder-Instruct and
inherit its license terms.

## Citation

Citation entry will be added on publication. Until then, please cite the repository
URL and the paper title above.
