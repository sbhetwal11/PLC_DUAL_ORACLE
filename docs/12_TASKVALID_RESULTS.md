# Task-valid metric & construct-validity experiments (DeepReview round 2)

All computed locally on CPU via the real WSL harness (MATIEC iec2c + nuXmv 2.2.0 +
scenario interpreter). Scripts in `analysis/`; raw JSON in `results/`. No GPU used.

## 1. Degenerate baselines (`analysis/baselines.py` → `results/baselines.json`)

Built by reusing each reference's declaration block and replacing only the body.
Four dimensions over 22 tasks:

| baseline    | compile | invariant | scenario | **task-valid** |
|-------------|---------|-----------|----------|----------------|
| all-off     | 22/22 (1.000) | 20/22 (0.909) | 0/22 (0.000) | **0/22 (0.000)** |
| all-on      | 22/22 (1.000) | 1/22 (0.045)  | 0/22 (0.000) | **0/22 (0.000)** |
| empty-body  | 0/22 (0.000)  | 0/22 (0.000)  | 0/22 (0.000) | **0/22 (0.000)** |

- all-off passes invariants on 20 tasks (per-tier easy 5/7, medium 11/11, hard 4/4) but
  fails **every** scenario → task-valid 0.000. This is the construct-validity fix (B1/B4).
- all-on satisfies invariants only on E05 (1/22).
- empty-body (declarations, no statements) is **rejected by MATIEC** (0/22 compile).

## 2. Task-valid API panel (`analysis/taskvalid.py` → `results/taskvalid.json`)

Re-scored the saved single-sample (n=1) programs with the real harness:

| model              | compile | invariant | scenario | **task-valid** |
|--------------------|---------|-----------|----------|----------------|
| reference (sanity) | 1.000   | 1.000     | 1.000    | **1.000**      |
| grok-3†            | 0.909   | 0.682     | 0.682    | **0.545**      |
| claude-sonnet-4-6  | 1.000   | 0.682     | 0.545    | **0.545**      |
| gemini-2.5-flash   | 0.182   | 0.182     | 0.182    | **0.182**      |
| gpt-4o             | 0.136   | 0.091     | 0.227    | **0.091**      |

- Every model beats the inert baseline (0.000) on task-valid → the "doing nothing beats
  every model" failure is removed once scenarios are in the metric.
- Orthogonal taxonomy (M9): translator "supported" on all 22 for every model; MATIEC
  rejections grok 2, claude 0, gemini 18, gpt-4o 19.
- Translator-rejected-but-MATIEC-accepted (integer-range/subset, M7): **0** in this panel.
- NOTE: n=1 single sample (n=10 raw programs were not cached). The n=10 pass@k task-valid
  rerun of the API panel remains to be done (needs a consistent API re-query, not a GPU).

## 3. Mutation analysis (`analysis/mutation.py` → `results/mutation.json`)

Syntactic mutants of the 22 references; **384 compiling mutants** kept:

| dimension                                   | count | rate  |
|---------------------------------------------|-------|-------|
| killed by invariants                        | 172   | 0.448 |
| killed by scenarios                         | 268   | 0.698 |
| killed by EITHER                            | 294   | 0.766 |
| **invariant-blind (scenario-only) kills**   | **122** | **0.318** |
| survived both (possible equivalents)        | 90    | 0.234 |

- 31.8% of compiling mutants pass **all** safety invariants yet fail a scenario → the
  invariant-only metric is blind to nearly a third of detectable functional faults (M22/M23/B1).
- This exercised the ST→SMV translator on 384 mutant programs, far beyond the original
  "22 refs + 1 mutation each" (partial answer to B6; full interp/SMV/MATIEC-C scan-trace
  equivalence + a mechanized proof remain).

## 4. Per-property vacuity (`analysis/vacuity.py` → `results/vacuity.json`)

71 properties:
- vacuously satisfied by all-off: **69 (0.972)**; not vacuous: 2 (E02.P2, E05.P1).
- positive-output obligations: **2**.
- forms: guard→¬out 30, mutual-exclusion 13, output→precondition ("other") 24,
  input-only (Count≤3) 2, positive-obligation 2.

Confirms the one-sided property design (M22) and explains why all-off scores 69/71.

## Remaining experiments (NEED THE 5090 - retraining/GPU inference)
- Fold functional-scenario reward into GRPO and **rerun all training conditions** (B1/B4).
- Filtering ablation: unfiltered / compile-only / property-only / dual / random-size-matched (B3).
- Entropy causal experiment with a fixed prompt set + entropy regularization (M13).
- ≥5 seeds for principal training comparisons (M16).
- Repair controls: trace-removal / trace-shuffle / property-only (M19).
- Fixed-frontier-set RL control (M20).
- Best-of-k / iterative-repair inference baseline vs trained models at matched oracle budget (B7).
- Output-activity / all-off-equivalence analysis of the **trained** policies (needs GPU sampling) (B4).
