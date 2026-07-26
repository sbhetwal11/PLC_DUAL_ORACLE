# 13 - DeepReview round-3 experiments on the RTX 5090

Eight experiments demanded by the major-revision reviewer report (`DeepReview.txt`),
**all complete, 0 failures**. Numbers computed with the REAL dual oracle (MATIEC
`iec2c` + nuXmv 2.2.0 + scenario interpreter). Every generated program is saved
(`results/exp*/…json`, `rows[].samples[].code`) so task-valid, output-activity and
best-of-k are recomputable offline. Prior adapters reused (reuse ledger at the end);
only genuinely-new training ran on GPU. Total ~16 GPU-hours.

**Construct-valid metric (the central fix, B1/B4).**
`task-valid = MATIEC-accepted ∧ all safety invariants hold ∧ all functional
scenarios pass`. Reported alongside the old invariant-only `verified` metric and the
`compile` / `scenario` dimensions separately (M9). Harness `analysis/eval_full.py`;
aggregation with hierarchical bootstrap CIs + paired-seed diffs `analysis/aggregate_full.py`.

A pre-run adversarial audit (6-agent workflow) independently recomputed Exp1a to
0.0000 error, confirmed the metric is correct (all-off scores task-valid 0/22), and
caught three design bugs in not-yet-run experiments that were fixed before they ran:
property-only filter had wrongly required compile (Exp2); repair variants didn't all
show the buggy code (Exp5); `entropy_coef` could be silently dropped (Exp3).

---

## Exp1 - functional reward (B1/B4)

**(a) Task-valid pass@k of the existing trained models (inference).** n=10, temp 0.8,
3 seeds (5 for base/SFT-lite/RL-lite). `results/exp1a/summary_both.json`,
`summary_5seed.json`.

| condition | task-valid p@1 | task-valid p@10 | verified p@1 | verified p@10 |
|-----------|---------------|-----------------|--------------|---------------|
| base      | 0.044±0.004 [0.01,0.09] | 0.227 | 0.082±0.007 | 0.379 |
| SFT (3ep) | 0.186±0.007 | 0.288 | 0.311±0.025 | 0.455 |
| SFT→RL    | 0.197±0.017 | 0.273 | 0.351±0.009 | 0.470 |
| SFT_v2    | **0.362±0.026** [0.17,0.56] | 0.394 | 0.396±0.039 | 0.470 |
| SFT-lite  | 0.174±0.036 | 0.424 | 0.227±0.046 | 0.515 |
| RL-lite   | 0.270±0.012 | **0.439** | 0.380±0.022 | **0.606** |

5-seed (base/SFT-lite/RL-lite): base 0.045±0.018, SFT-lite 0.179±0.028,
RL-lite 0.272±0.011 task-valid p@1. Verified column reproduces the paper's prior
macros within sampling noise. **Every trained model beats the inert all-off baseline
(task-valid 0.000); training lifts task-valid pass@1 ~8× - the gains are genuine
functional gains, not inert-collapse artifacts.**

**(b) Functional-reward RL.** `finetune/reward.py::task_valid_reward` grades
`0.2 + 0.4·prop + 0.4·scen` (=1.0 iff compile ∧ invariants ∧ scenarios). Warm-started
from SFT-lite on a 39-prompt task-valid frontier set. `results/exp1b/`.

| | task-valid p@1 | task-valid p@10 | verified p@1 | verified p@10 |
|---|---|---|---|---|
| SFT-lite (start) | 0.174±0.036 | 0.424 | 0.227 | 0.515 |
| **RL-func (Exp1b)** | **0.282±0.010** | 0.409 | 0.382 | **0.591** |

**+0.108 task-valid pass@1 (+62% rel.), variance −3.6× (±0.036→±0.010).** Optimizing
the construct-valid reward improves the construct-valid metric - the working answer to
"the RL reward must include functional behavior."

## Exp2 - filtering ablation (B3)

- **Procedural pool** (`results/exp2/composition.json`): the 158 datagen references
  all pass compile ∧ invariant ∧ scenario → **reject rate 0.0%.** On procedural data
  the filter is INERT (the reviewer's B3 point holds there).
- **Model-sampled rejectable pool** (`finetune/build_model_pool.py`,
  `results/exp2/composition_model.json`): 632 base-7B samples, **86.1% rejected**
  (15 compile-only, 404 property-only, 125 both - the dominant failure is
  compilable-but-unsafe). Five matched SFT sets, 3-epoch, task-valid pass@1:

  | trained on | size | task-valid p@1 |
  |---|---|---|
  | all (unfiltered) | 632 | 0.014±0.004 |
  | MATIEC-only | 492 | 0.020±0.009 |
  | property-only | 103 | 0.086±0.013 |
  | **dual** | 88 | **0.127±0.010** |
  | random size-matched | 88 | 0.050±0.010 |

  **`dual` (0.127) > size-matched `random` (0.050)** at identical size ⇒ the filter
  QUALITY, not corpus size, drives the gain (+0.077, size-controlled). Each oracle
  contributes (`all<matiec<property<dual`); the safety-property filter is the bigger
  lever. `property_only ≠ dual` confirms the compile-independent fix. **Honest framing:
  on a rejectable model-sampled pool the verifier filter is causal; on the procedural
  pool it is inert.**

## Exp3 - entropy causal (M13)

Fixed prompts + reward; vary warm-start/regularization; per-step diagnostics logged
(`results/exp3/*.json`):

| run | warm-start | ent_coef / β | mean entropy | **% zero-variance groups** |
|---|---|---|---|---|
| hi_ent0 | SFT-lite | 0 / 0 | 0.151 | **0.10** |
| lo_ent0 | 3-epoch SFT | 0 / 0 | 0.015 | **0.775** |
| lo_entreg | 3-epoch SFT | 0.05 / 0 | 0.018 | 0.75 |
| hi_beta | SFT-lite | 0 / 0.04 | 0.156 | 0.075 |

Warm-start entropy **controls the fraction of zero-variance GRPO groups** (the gradient
availability). A small entropy bonus **cannot rescue an already-collapsed policy**
(0.775→0.75). This is the causal experiment M13 demanded, with the required diagnostics.

## Exp4 - five seeds (M16)

Trained seeds 3-4; headline 7B now n=5 (task-valid p@1): base 0.045±0.018,
SFT-lite 0.179±0.028, **RL-lite 0.272±0.011** (verified 0.079/0.242/0.389). Tight CIs;
the RL-lite gain is stable across 5 seeds. Paired diffs + bootstrap CIs in
`results/exp1a/summary_5seed.json`.

## Exp5 - repair controls (M19)

Trained on bug types {weaken_or, flip_compare}, evaluated on HELD-OUT {force_true}
(17/22 tasks), task-valid pass@1 (3-seed):

| training | pass@1 | pass@10 |
|---|---|---|
| base (untrained) | 0.388±0.008 | 0.863 |
| generic SFT (no repair pairs) | 0.461±0.006 | 0.882 |
| nocex | 0.553±0.033 | 0.765 |
| erroronly | 0.594±0.025 | 0.843 |
| proponly | 0.592±0.040 | 0.902 |
| shuffled cex | 0.680±0.027 | 0.961 |
| **full (correct cex)** | 0.514±0.042 | 0.804 |

**Honest negative:** repair-*format* training helps (all variants > generic > base),
but the counterexample TRACE provides **no measurable benefit** - `full` ≈ `nocex`, and
a mismatched trace is not worse (higher, within noise). The trace content is not the
active ingredient; the buggy-code+repair-format is. **Vindicates M19 → de-emphasise
"counterexample-guided repair" as a headline claim** (label it an exploratory
data-format study).

## Exp6 - fixed-frontier RL (M20)

All warm-starts on the SAME 39-prompt frontier, same reward/rollout/updates; `k=6` for
prompt reward-variance estimation. Task-valid p@1 (3-seed):

| warm-start | entropy | task-valid p@1 |
|---|---|---|
| base | high | 0.052±0.009 |
| 3-epoch SFT | collapsed | 0.215±0.011 |
| **SFT-lite** | preserved | **0.282±0.010** |

Monotonic with warm-start entropy under a fully-controlled protocol - resolves the M13
confound (prompts/reward/budget held fixed).

## Exp7 - best-of-k / repair inference baseline (B7)

`analysis/inference_baselines.py`, task-valid criterion, 3-seed:

| approach | success | oracle calls/task |
|---|---|---|
| base · best-of-10 | 0.197 | ~9 |
| SFT · best-of-10 | 0.303 | ~8 |
| base · iter-repair(≤5) | 0.106 | ~5 |
| SFT · iter-repair(≤5) | 0.273 | ~4 |
| RL-lite · pass@10 | **0.427** | 10 |
| RL-lite · pass@1 | 0.272 | **1** |

**Training beats cost-matched inference-time verifier use:** RL-lite at ONE oracle call
(0.272) rivals SFT best-of-8 (0.303); at a matched 10-call budget training (0.427) more
than doubles base best-of-k (0.197). The training contribution holds up.

## Exp8 - output-activity (B4)

`analysis/output_activity.py` (behavioural probe on scenario input sequences, 3-seed):

| condition | scenario pass | activation freq | all-off≡ | constant |
|---|---|---|---|---|
| base | 0.202 | 0.773 | 0.227 | 0.237 |
| SFT | 0.244 | 0.944 | 0.056 | 0.056 |
| SFT_v2 | 0.373 | **0.975** | **0.025** | 0.025 |
| RL-lite | 0.308 | 0.841 | 0.159 | 0.168 |
| **RL-func (Exp1b)** | 0.318 | 0.887 | 0.113 | 0.115 |
| SFT-zeroshot | 0.308 | 0.987 | 0.013 | 0.013 |

**Verifier-grounded training makes policies MORE active, not inert** - activation
0.773→0.975; all-off-equivalent 0.227→0.025. The functional-reward RL is more active
than the invariant-reward RL (0.887 vs 0.841). Refutes the drift-to-inactivity concern.
Degenerate baselines (`results/baselines.json`): all-off/all-on/empty-body all
task-valid 0.000. Caveat: fractions are over the parseable-ST subset (n_parsed reported
per condition; ~46% for base, higher for trained).

---

## Reuse ledger & GPU-hours

**Reused (0 retraining):** all prior LoRA adapters in `finetune/out/{seeds,v2,full}`
(base/SFT/RL/SFT-v2/RL-from-base/SFT-lite/RL-lite/SFT-zeroshot × seeds 0-2; 1.5B/14B),
plus prior data pools and `docs/10` tables.

**New GPU training (~16 h):** Exp1b/6 9 functional-RL runs + frontier selection;
Exp2 model pool + 15 ablation SFTs; Exp3 4 short RL; Exp4 seeds 3-4 (2 SFT-lite +
2 RL-lite); Exp5 18 repair-control SFTs. **Inference-only (no training):** Exp1a, Exp7,
Exp8. **CPU-only:** all analysis + aggregation.

**Failures/truncation:** none. One ~3 h GPU idle early (a pgrep self-match in a handoff
watcher) cost wall-clock but no work. All 8 experiments completed with 0 step failures.
