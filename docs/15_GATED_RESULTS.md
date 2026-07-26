# 15 - Critical-property hard-gated reward RL: results

Executed on a single RTX 5090, **2026-07-20** (~2.6 h wall-clock). This is the paper's
last "future work" computation - critical-property gating - now run and folded into the
paper. Raw data: **`results/exp_gated/`**. Plan/reproduce: `docs/14_VM_PLAN.md`.

> All numbers below are copied from `results/exp_gated/` (verified against the raw
> per-seed `rlgated_sftlite_s{0,1,2}.json` by recomputing unbiased pass@k). Real data only.

---

## 1. Protocol

- **Reward.** The Exp1b functional (task-valid) reward `r_tv` (Eq. 3 of the paper),
  **hard-gated**: reward = `min(base, 0.1)` whenever **any** critical-severity property
  is not confirmed passing. **36 of the 71** benchmark properties are `severity=critical`
  (verified: `python - <<'PY' ...` over `benchmark/tasks/*/*/meta.json` → `props 71
  critical 36`). Intuition: a completion that misses a critical interlock cannot bank
  compile/scenario credit.
- **Algorithm.** GRPO, **50 steps** (matched to Exp1b `rlfunc_sftlite`), `num_gen 8`,
  `grad_accum 4`, rollout temperature **1.0**.
- **Warm start.** The entropy-preserving SFT-lite adapters, seeds **{0,1,2}**
  (`finetune/out/full/sftlite_s{0,1,2}`).
- **Frontier prompts.** `finetune/data/rl_prompts_taskvalid.jsonl` - the **same 39-prompt**
  set as Exp1b.
- **Evaluation.** n=**10** samples/task at temperature **0.8**, all **22** tasks; dual
  oracle (MATIEC compile + nuXmv verify) + functional scenarios. SD = **population SD**
  across the 3 training seeds (identical convention to every existing training-table row).
- **Stage tag:** `rlgated_sftlite`.

Only the **reward** differs from the Exp1b functional-reward run `rlfunc_sftlite`; warm
start, seeds, step count, prompt set, decoding, and eval are identical - so the paired
per-seed comparison isolates the gate.

---

## 2. Headline numbers (3 seeds, mean ± population SD)

| metric | pass@1 | pass@3 | pass@5 | pass@10 |
|---|---|---|---|---|
| **all-checks-pass** (task-valid) | 0.292 ± 0.015 | 0.380 ± 0.018 | 0.403 ± 0.018 | 0.424 ± 0.021 |
| **compile-and-invariant** ("verified") | 0.411 ± 0.008 | 0.535 ± 0.014 | 0.586 ± 0.011 | 0.652 ± 0.021 |

Per-seed pass@1 (from `gated_summary.json`):

| seed | task-valid pass@1 | verified pass@1 |
|---|---|---|
| 0 | 0.2864 | 0.4182 |
| 1 | 0.3136 | 0.4136 |
| 2 | 0.2773 | 0.4000 |

Bootstrap pass@1 (task-resampled, from summary): task-valid 0.291 [0.136, 0.450];
verified 0.410 [0.241, 0.586].

---

## 3. Paired comparison vs Exp1b `rlfunc_sftlite` (same seeds)

Per-seed pass@1 differences (gated − functional):

| seed | task-valid Δ | verified Δ |
|---|---|---|
| 0 | −0.009 | +0.032 |
| 1 | +0.036 | +0.032 |
| 2 | +0.005 | +0.023 |
| **paired mean** | **+0.011** (SD 0.019) | **+0.029** (SD 0.004) |

pass@10 paired: task-valid **+0.015** (SD 0.021); verified **+0.061** (SD 0.057, noisy).

- **Task-valid:** mixed signs, +0.011 with SD larger than the mean → **within noise** at
  three seeds. No task-valid improvement is claimed.
- **Compile-and-invariant:** +0.029, **positive in every one of the three seeds**, tight
  SD (0.004) → a **small but seed-consistent** gain.

---

## 4. Training sanity (reward learned)

Mean GRPO reward, first-5-step → last-5-step (`metrics_sftlite_s{0,1,2}.json`):

| seed | first-5 | last-5 |
|---|---|---|
| 0 | 0.39 | 0.66 |
| 1 | 0.23 | 0.78 |
| 2 | 0.35 | 0.69 |

Reward rose across all three seeds; the gated objective is learnable and did not collapse.

---

## 5. Provenance

- **`results/exp_gated/ENV.txt`** (recorded Mon Jul 20 02:26:22 UTC 2026):
 - Oracle binaries present: nuXmv-2.2.0, MATIEC `iec2c` (plcbench check-tools: both available).
 - **Oracle end-to-end pre-run sanity** on 4 reference tasks - all `compile=OK verify=OK`,
    all props/scenarios passing (E01 motor interlock, M06 burner purge, M11 dosing counter,
    H03 batch reactor).
 - **Gated reward unit test: 9/9 pass** (exit 0).
 - STEPS=50; GPU = RTX 5090 (580.142, 32607 MiB); Python 3.12.3; trl 1.8.0, transformers
    5.14.1, torch 2.11.0+cu128 (full `pip freeze` in the file).
- **`results/exp_gated/STATUS.log`** timestamps (UTC 2026-07-20):
  02:19:12 start → s0 train/eval → s1 train/eval → s2 train/eval → 04:54:16 done
  (aggregate written). ~2.6 h wall-clock, three seeds back-to-back.
- **Outputs:** `rlgated_sftlite_s{0,1,2}.json` (raw completions + verdicts),
  `metrics_sftlite_s{0,1,2}.json`, `gated_summary.json`, `logs_*`, `run.out`.

---

## 6. Honest interpretation

**Hard-gating the reward on the 36 critical properties costs nothing on all-checks-pass**
(paired +0.011 pass@1, within noise at three seeds) **and yields a small but
seed-consistent improvement on compile-and-invariant compliance** (paired +0.029 pass@1,
SD 0.004, positive in every seed).

Scope / what is **not** claimed:
- **No task-valid improvement** - +0.011 is within noise (mixed signs, SD > mean).
- **No safety-significance claim** beyond the stated paired means - three seeds only.
- **Does not change the paper's best-system statement.** On the primary all-checks-pass
  metric, SFT-v2 (0.362 pass@1) still leads; the gated run is 0.292. Its
  compile-and-invariant pass@1 (0.411) is nominally the highest among trained conditions,
  but at a lower all-checks-pass rate.

**Where it lands in the paper:**
- Supplement Table **S-XIV** (`tab:tvtrainfull`): added row `RL (crit. gated)`
  0.292/0.424 task-valid, 0.411/0.652 verified.
- Supplement Sec. **S.XVIII** (`ssec:fulltrain`): "Critical-property-gated reward"
  paragraph after the matched-seed comparison.
- `main.tex`: Threats "Reward hacking" passage and §VII reward-definition + the
  entropy/structural caveat updated from "gating remains future work" to reporting this
  result (liveness obligations still remain future work).
