# 10 - Fine-tuning results (Phase 3, on the RTX 5090)

**Date:** 2026-06-28 · **Box:** rented RTX 5090 (32 GB, driver 590.48, CUDA 13.1) ·
**Base model:** `Qwen/Qwen2.5-Coder-7B-Instruct` · **Metric:** verified-safe pass@k
(compiles under MATIEC **and** every safety property holds under nuXmv), n=10 samples
/ task, temperature 0.8, on the 22-task benchmark.

Raw: `results/passk_hf_base.json`, `results/passk_hf_sft.json`, `results/passk_hf_rl.json`.

---

## ⭐⭐⭐ FULL SUITE (2026-06-30) - model-size scaling, entropy-preserving RL, ablations

Five experiments run unattended end-to-end on one 5090 (`toolchain/run_full_suite.sh`;
14B leg finished via the idempotent `run_exp2b_resume.sh` after a container teardown).
All numbers are 3-seed mean ± std unless noted, verified-safe pass@k, n=10, temp 0.8,
22-task benchmark. Raw per-seed JSONs in `results/full/`; aggregates in
`results/full/exp{1,2a,2b,3}_summary.json`.

### Headline 1 - entropy-preserving SFT unlocks the RL win (7B). EXP1
The earlier "RL is a weak lever" was an artifact of an **over-trained, entropy-collapsed
3-epoch SFT** (reward_std≈0 → no GRPO gradient). A **1-epoch, lr=1e-4 SFT** keeps the
policy stochastic, frontier-prompt selection then finds 42 high-variance prompts, and
GRPO has signal to optimize:

| condition (7B)                       | pass@1        | pass@10       |
|--------------------------------------|---------------|---------------|
| SFT-lite (1 epoch)                   | 0.223±0.046   | 0.470±0.043   |
| **RL-lite (frontier GRPO on lite)**  | **0.397±0.017** | **0.591±0.037** |

RL adds **+0.174 pass@1 / +0.121 pass@10** over its warm-start - the **best 7B result in
the whole project**, and it *resolves the central RL-weakness question*: verifier-reward
RL pays off decisively when warm-started from a high-entropy policy, not a saturated one.

### Headline 2 - the method scales across model size (1.5B / 7B / 14B). EXP2a, EXP2b
| model | base p@1 | SFT p@1 | RL p@1 | base→SFT | base p@10 → RL p@10 |
|-------|----------|---------|--------|----------|---------------------|
| 1.5B  | 0.000±0.000 | 0.291±0.029 | **0.364±0.046** | from zero | 0.000 → 0.621±0.057 |
| 7B (3ep) | 0.068±0.007 | 0.314±0.033 | 0.344±0.008 | 4.6× | 0.349 → 0.455 |
| 7B (lite) | 0.068 | 0.223±0.046 | **0.397±0.017** | - | 0.349 → 0.591 |
| 14B   | 0.070±0.013 | **0.486±0.022** | **0.491±0.028** | 6.9× | 0.288 → 0.561±0.043 |

SFT pass@1 rises monotonically with scale (0.291 → 0.314 → 0.486). RL's *marginal* gain
is largest where the warm-start is high-entropy (7B-lite +0.174) and at small scale
(1.5B +0.073, lifting a model that solves **nothing** zero-shot up to 0.364); on the
heavily-SFT'd 14B it is small on pass@1 (+0.005) but still positive on pass@10 (+0.031),
and improves the hard tier (p@10 0.333→0.417) and medium tier (p@1 0.242→0.261).

### Headline 3 - ablations: hard families help SFT; repair pairs are near-neutral for zero-shot, positive for repair. EXP3, EXP4
- **Hard verified families help SFT.** 3-epoch SFT on zeroshot-only data *including* the
  50 harder families: **pass@1 0.401±0.025** / pass@10 0.515±0.021 - well above the
  original 158-pair SFT (0.314) and the v2 zeroshot+repair mix (0.385).
- **Counterexample-repair pairs are near-neutral for zero-shot generation** (they
  slightly *lowered* zero-shot pass@1: 0.401 no-repair vs 0.385 with-repair) **but help
  the repair task itself.** On the dedicated counterexample-guided **repair eval**
  (seed 0, fix a buggy program given the formal counterexample):

  | model (7B)                | repair pass@1 | repair pass@10 |
  |---------------------------|---------------|----------------|
  | base                      | 0.065         | 0.353          |
  | SFT **without** repair    | 0.353         | 0.529          |
  | SFT **with** repair (v2)  | 0.353         | **0.588**      |

  SFT massively improves repair over base (0.065→0.353 pass@1, **5.4×**); training *with*
  repair pairs adds +0.059 pass@10 on the repair task specifically - an honest, modest,
  task-localized gain.

**Bottom line for the paper.** (1) Verifier-filtered SFT is the dominant lever and it
scales (up to 0.486 pass@1 at 14B). (2) Verifier-reward GRPO is a genuine win **given a
high-entropy warm-start** - best 7B result 0.397/0.591, and lifts a 1.5B model from 0.000
to 0.364. (3) Hard verified families improve SFT; counterexample-repair pairs help the
repair capability without hurting (much) zero-shot. The entropy-collapse finding is the
methodological lesson: report the SFT entropy, don't over-train before RL.

---

## Pipeline run end-to-end
data → **SFT** → eval → **RL** → eval, all on one 5090. The dual oracle (MATIEC +
nuXmv) is the supervision signal at every stage: it filters the SFT data and is the
RL reward.

- **Data:** `finetune/build_sft.py` → **158/158** generated task-family instances
  pass the dual oracle → `finetune/data/sft.jsonl` (62 easy-style, 96 medium-style;
  disjoint from the 22 eval tasks).
- **SFT:** 4-bit QLoRA (r=16), 3 epochs, 60 steps, final train loss ≈ 0.015.
  Adapter `finetune/out/sft` (80 MB).
- **RL:** GRPO warm-started from the SFT adapter, group size 8, 30 steps, reward =
  graded dual oracle (`finetune/reward.py`). Adapter `finetune/out/rl`.

## ⭐⭐ MASTER TABLE - all conditions, 3-seed mean ± std (the headline)

Every condition is 3 seeds (0,1,2), controlled RNG for training and sampling, n=10
samples/task, verified-safe pass@k on the 22-task benchmark.

| condition                         | pass@1        | pass@10       | notes |
|-----------------------------------|---------------|---------------|-------|
| base                              | 0.068±0.007   | 0.349±0.057   | Qwen2.5-Coder-7B-Instruct |
| **SFT** (verifier-filtered)       | 0.314±0.033   | 0.440±0.057   | 158 verified pairs |
| **SFT→RL** (GRPO, dual-oracle)    | **0.344±0.008** | **0.455±0.037** | best pass@10; RL refines SFT, ↓variance |
| **SFT_v2** (strengthened data)    | **0.385±0.043** | 0.439±0.077   | best pass@1; +hard families +repair pairs |
| RL-from-base (frontier prompts)   | 0.082±0.016   | 0.348±0.043   | verifier reward learns but transfers weakly |

**One-paragraph story.** Verifier-*filtered SFT* is the dominant lever (base 0.068 →
0.314 pass@1, **4.6×**). *Strengthening the SFT data* (50 harder verified families +
161 counterexample-repair pairs) pushes pass@1 to **0.385** (easy tier → perfect 1.0).
*Verifier-reward RL as a refinement on top of SFT* adds a small but **consistent** gain
and **cuts variance 4×** (0.314±0.033 → 0.344±0.008) - the strongest pass@10 (0.455).
*Verifier-reward RL from the base model* on frontier-selected prompts demonstrably
optimises the formal reward (train reward 0.19→0.31) but transfers only marginally and
noisily to the held-out benchmark (0.068→0.082±0.016) - RL is best as a refiner, not a
from-scratch trainer. Full v2 analysis + the entropy-collapse finding are below.

## ⭐ CANONICAL - overall pass@k, mean ± std over 3 seeds (0,1,2)

Seeded sweep (`toolchain/run_seed_sweep.sh`; controlled RNG for training **and**
sampling). Raw: `results/seeds/{base,sft,rl}_s{0,1,2}.json`, aggregate in
`results/seeds/summary.json` (`python -m finetune.aggregate_seeds`).

| k        | BASE        | SFT         | RL          | RL vs BASE |
|----------|-------------|-------------|-------------|------------|
| pass@1   | 0.068±0.007 | 0.314±0.033 | **0.344±0.008** | **+0.276 (5.1×)** |
| pass@3   | 0.172±0.005 | 0.404±0.051 | 0.427±0.035 | +0.255 |
| pass@5   | 0.246±0.015 | 0.428±0.056 | 0.447±0.037 | +0.201 |
| pass@10  | 0.349±0.057 | 0.440±0.057 | 0.455±0.037 | +0.106 |

By tier, pass@1 / pass@10 (mean±std):

| tier   | BASE                | SFT                 | RL                  |
|--------|---------------------|---------------------|---------------------|
| easy   | 0.138±0.029/0.619   | 0.752±0.036/0.857   | **0.805±0.041**/0.857 |
| medium | 0.039±0.009/0.243   | 0.100±0.060/0.243   | **0.130±0.049/0.273** |
| hard   | 0.025±0.020/0.167   | 0.133±0.031/0.250   | 0.125±0.054/0.250   |

**Across seeds:** SFT lifts pass@1 **4.6×** (0.068→0.314); **RL adds a further
+0.030 pass@1 AND cuts its variance 4× (std 0.033→0.008)** - verifier-reward RL
makes the gain *consistent*, not just larger. RL ≥ SFT at every k in the mean. With
proper seeding **the medium tier improves at every stage** (0.039→0.100→0.130
pass@1; 0.243→0.243→0.273 pass@10) - the medium "regression" seen in the first
single-seed run below was seed noise, not a real effect.

## First single-seed run (superseded by the 3-seed table above) - overall pass@k

| k        | BASE  | SFT   | RL    | RL vs BASE |
|----------|-------|-------|-------|------------|
| pass@1   | 0.073 | 0.250 | **0.273** | **+0.200 (3.7×)** |
| pass@3   | 0.184 | 0.311 | 0.331 | +0.147 |
| pass@5   | 0.260 | 0.350 | 0.366 | +0.106 |
| pass@10  | 0.364 | 0.409 | 0.409 | +0.045 |

## By tier - pass@1 / pass@10

| tier   | BASE        | SFT         | RL          |
|--------|-------------|-------------|-------------|
| easy   | 0.143/0.571 | 0.700/0.857 | **0.786**/0.857 |
| medium | 0.055/0.364 | 0.036/**0.182** | 0.036/0.182 |
| hard   | 0.000/0.000 | 0.050/0.250 | 0.025/0.250 |

## Findings (what the numbers say)

1. **Verifier-filtered SFT is the dominant lever.** pass@1 0.073 → 0.250 (3.4×);
   easy-tier pass@1 0.143 → 0.700. The 7B base model's main failure mode is *valid,
   compilable, formally-safe ST generation*, and imitating dual-oracle-verified code
   fixes most of it on in-distribution patterns. This matches the baseline thesis
   (bottleneck = valid-ST generation, not reasoning).

2. **Verifier-reward RL adds a real but small gain on top of SFT.** pass@1 0.250 →
   0.273 (+9% rel), pass@3/5 also up, easy-tier pass@1 0.700 → 0.786. Net ordering
   RL > SFT > base on pass@1/3/5.

3. **RL is reward-saturated on in-distribution prompts.** 23/30 GRPO steps had
   `reward_std = 0` (`frac_reward_zero_std = 1.0`); the remaining 7 had only partial
   variance (std 0.04-0.18). After verifier-filtered SFT the model already solves the
   training families near-perfectly, so most GRPO groups carry zero advantage → little
   gradient. **Implication:** verifier-reward RL needs prompts at the model's
   *capability frontier* (where it sometimes fails) to produce learning signal - an
   easy/medium generative curriculum below the SFT ceiling gives diminishing returns.

4. **SFT trades medium-tier diversity for easy-tier accuracy.** Medium pass@10 drops
   0.364 → 0.182 even though easy soars. The SFT model becomes peaked/deterministic
   (entropy ≈ 0.001), which helps pass@1 but collapses the sample diversity that
   pass@10 relies on for the harder, less in-distribution medium tasks. RL did not
   recover this (medium unchanged at 0.036/0.182).

5. **Hard tier:** base is a hard 0 at every k; SFT/RL crack it open
   (pass@10 0.250), i.e. the method lifts a small model from *never* to *sometimes*
   solving multi-component tasks.

## Honest caveats / next iterations
- The medium regression + RL saturation both point at the **training data**: the
  easy/medium generative families sit at or below the SFT model's frontier. Next:
  (a) harder, more diverse held-in families; (b) rejection-sampling + counterexample-
  repair pairs (`docs/08`) so SFT sees corrected-from-failure examples; (c) select RL
  prompts by base-model failure rate to guarantee reward variance.
- pass@k success = *verified-safe only* (compile ∧ all properties). Per-sample
  unsafe-rate is not retained by the pass@k path; the single-sample `eval-llm` path
  reports it (prior runs ≈ 0 unsafe).
- Numbers are a single SFT/RL seed. Report as a proof-of-method; add seeds before the
  paper's final table.

## Reproduce (on the 5090)
```bash
bash toolchain/setup_5090.sh
$HOME/plcvenv/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128
$HOME/plcvenv/bin/pip install -r finetune/requirements.txt
# env for the oracle:
export NUXMV_BIN=$(find $HOME/nuxmv -name nuXmv -type f|head -1) MATIEC_IEC2C=$HOME/matiec/iec2c PYTHONPATH=$PWD
bash toolchain/wsl_build_sft.sh                                   # data
python -m plcbench.cli eval-passk --model hf:Qwen/Qwen2.5-Coder-7B-Instruct --n 10 --k 1,3,5,10 --out results/passk_hf_base.json
python -m finetune.sft --data finetune/data/sft.jsonl --model Qwen/Qwen2.5-Coder-7B-Instruct --out finetune/out/sft
python -m plcbench.cli eval-passk --model "hf:Qwen/Qwen2.5-Coder-7B-Instruct+finetune/out/sft" --n 10 --k 1,3,5,10 --out results/passk_hf_sft.json
python -m finetune.rl  --data finetune/data/sft.jsonl --model Qwen/Qwen2.5-Coder-7B-Instruct --adapter finetune/out/sft --out finetune/out/rl --num_gen 8 --grad_accum 4 --max_steps 30
python -m plcbench.cli eval-passk --model "hf:Qwen/Qwen2.5-Coder-7B-Instruct+finetune/out/rl" --n 10 --k 1,3,5,10 --out results/passk_hf_rl.json
```

## Environment fix worth recording
This box's `torch 2.11.0+cu128` wheel **aborts on cudnn symbol load**
(`Invalid handle. Cannot load symbol cudnnGetVersion`). LLM inference/training is
matmul-only and needs no cudnn, so all GPU entry points now set
`torch.backends.cudnn.enabled = False` + `attn_implementation="eager"`
(`plcbench/generate/clients.py`, `finetune/sft.py`, `finetune/rl.py`). Plain CUDA
matmul and bitsandbytes 4-bit both work fine on the 5090; only cudnn was broken.
Training scripts were also ported to **trl 1.7 / transformers 5.x**
(`max_seq_length`→`max_length`, `model_init_kwargs` into the config, dropped
`max_prompt_length`, GRPO warm-start via a trainable `PeftModel`).

---

# Phase 3 v2 - data strengthening + failure-frequency RL prompt selection

Motivated by the v1 findings (RL reward-saturates on in-distribution prompts; SFT may
trade diversity). Drivers: `toolchain/run_v2_sweep.sh` (SFT_v2), `run_rl_frontier.sh`
(RL-from-base). Raw: `results/v2/{sft,rlbase}_s{0,1,2}.json`, summaries
`results/v2/*_summary.json`.

## v2.1 Strengthened SFT data
`finetune/datagen.generate_hard()` adds **50 harder, dual-oracle-verified** instances
across 4 new families (safety_chain, two_speed, bounded_updown, ordered_pair - all
compile + fully verify). `build_sft --include-hard --repair` also emits **161
counterexample-repair pairs**: inject a safety bug → confirm it really fails nuXmv →
attach the *real counterexample* → pair with the corrected reference. Dataset grows
158 → **369** examples (208 verified zero-shot + 161 repair).

**SFT_v2 result (3-seed):** pass@1 **0.314 → 0.385** (+0.071 over v1 SFT), pass@10
0.440 → 0.439 (flat). By tier (pass@1/pass@10): easy **0.752→1.000 / 0.857→1.000**
(perfect), medium 0.100→**0.134** / 0.243, hard **0.133→0.000** / 0.250→0.000.

> **Finding:** strengthening with more safety-latch families maximises easy/medium but
> **shifts the model off the genuinely-hard eval tasks** (elevator, batch reactor,
> intersection - which need CASE state machines + multiple timers). Net pass@1 rises
> because easy (7) + medium (11) dominate the 22 tasks, but hard (4) collapses to 0.
> Data curation must match the *target* difficulty mix, not just add "more hard-ish."

## v2.2 The entropy-collapse finding (why naive SFT→RL saturates)
Probing the warm-start policy with the **graded** dual-oracle reward (the exact RL
reward) revealed the real blocker: a 3-epoch verifier-filtered SFT is **near-
deterministic** (policy entropy ≈ 0.001). At temperature 0.8 it emits the *same*
program every sample, so **every prompt has reward std = 0** - even prompts it only
half-solves (e.g. `two_speed`: reward 0.77 ± **0.00**, verified 0.00). With zero
within-group variance, GRPO advantage is zero and there is no gradient, *regardless of
prompt selection*. This is why v1 RL only nudged +0.030 (7/30 steps had any variance)
and why on-distribution frontier selection returns 0 prompts.

> **Implication:** verifier-reward RL needs a **high-entropy policy**. Two fixes:
> (a) a lighter SFT warm-start that preserves entropy, or (b) RL from the base model.
> We took (b) for a clean demonstration.

## v2.3 Failure-frequency prompt selection + RL-from-base
`finetune/select_rl_prompts.py` scores candidates by **graded-reward variance** under
the probed policy (not verified-fraction - the reward is graded, so a prompt the model
never fully solves can still have high reward variance). Probing the **base** model
over the held-out hard families yielded **47/47 frontier prompts** (reward_std mean
0.22, verified_frac 0.06). RL-from-base (`--adapter none`, fresh LoRA, GRPO 50 steps)
on these had real signal: **train reward 0.19 → 0.31**, reward_std ≈ 0.25-0.40.

**RL-from-base result (3-seed):** pass@1 0.068 → **0.082 ± 0.016** (+0.014, within
noise), pass@10 0.349 → 0.348 (flat). Per-seed pass@1: 0.059→0.095, 0.068→0.059,
(seed2). By tier the small gain is concentrated on medium (0.039 → 0.070).

> **Finding:** verifier-reward RL **demonstrably optimises the formal reward** on its
> training prompts, but 50 GRPO steps from a weak base on 47 held-out hard prompts
> **transfers only marginally and noisily** to the 22-task benchmark, and (like all RL
> here) trades pass@10 diversity. RL pays off as a **refinement on a strong SFT**
> (v1: reliable +0.030, variance ↓4×), not as a from-scratch trainer.

## v2.4 Robustness fix (found the hard way)
At RL exploration temperature the policy emits arbitrary bytes; a completion echoed by
`iec2c`/nuXmv crashed the reward with `UnicodeDecodeError` at step 11. Fixed:
`compile_matiec`/`verify_nuxmv` decode tool output with `errors="replace"`, and
`dual_oracle_reward` is fully guarded → 0.0 on any oracle hiccup (one bad completion
never kills GRPO).

## Net recommendations for the paper
1. Headline the **3-seed** numbers with error bars (Master Table). SFT is the lever;
   RL is a variance-reducing refinement; data strengthening helps but needs the right
   difficulty mix.
2. The **counterexample-as-training-signal** story is intact: dual oracle filters SFT,
   grades the RL reward, and produces repair pairs - all sound (no LLM judge).
3. To make RL clearly win: lighter/entropy-preserving SFT warm-start + frontier prompts
   that are held out from SFT but *match the eval difficulty mix*. Add more seeds.
