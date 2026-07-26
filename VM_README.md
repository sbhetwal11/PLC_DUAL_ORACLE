# VM_README - one GPU job: critical-property hard-gated reward RL

This package is a **self-contained deployment zip** for a single rented RTX 5090 VM. It runs
**one** experiment - verifier-reward GRPO with a **safety-critical-gated** task-valid reward,
warm-started from the entropy-preserving SFT-lite adapters (seeds 0,1,2), then task-valid
pass@k eval on all 22 benchmark tasks. This closes the paper's open item
*"critical-property gating remains future work"* (`paper/PLC_DUAL_ORACLE/main.tex`).

**Everything else already exists in this package** - benchmark, oracles, prior adapters, and
all previously computed results. Do NOT re-run any completed experiment (see the
DO-NOT-RECOMPUTE manifest at the bottom).

## Canonical source note
This zip was built from the ONE canonical tree:
`...\ResearchPaper2\PLCCodeGenResearch_5090\PLCCodeGenResearch`.
A stale sibling tree (`...\ResearchPaper2\_5090_full\...`) exists on the source machine and
was deliberately **excluded**; nothing here comes from it.

## What is / isn't included
- INCLUDED: full `plcbench/ benchmark/ analysis/ toolchain/ docs/ external_testset_draft/
  results/ paper/PLC_DUAL_ORACLE/` (source + reference PDFs), all `finetune/` code + data,
  and ONLY the three warm-start adapters `finetune/out/full/sftlite_s{0,1,2}/`.
- EXCLUDED: every other `finetune/out/` checkpoint (not needed for the gated run; gigabytes),
  `__pycache__/`, `*.pyc`, LaTeX build litter (`.aux/.log/.out/.bbl/.blg`), any `.git`.

---

## 1. Setup on the VM

RTX 5090 = Blackwell sm_120, 32 GB → needs **CUDA 12.8+ / PyTorch cu128** (older wheels fall
back to CPU). Use a CUDA-12.8 template, Python 3.11. Unzip this package; `cd` into the repo
root (the dir containing this file), then:

```bash
# 1) Python venv at ~/plcvenv  (the scripts hard-code $HOME/plcvenv/bin/python)
python -m venv ~/plcvenv && source ~/plcvenv/bin/activate
~/plcvenv/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128
~/plcvenv/bin/pip install -r finetune/requirements.txt   # transformers 5.x / trl 1.7 / peft / bnb / datasets
~/plcvenv/bin/pip install -e .                            # makes plcbench importable (or export PYTHONPATH=$PWD)

# 2) Verification toolchain = the reward oracle. run_vm_gated.sh REQUIRES both of these to
#    resolve at these EXACT paths or the critical gate cannot verify:
#      NUXMV_BIN   -> auto-found under  $HOME/nuxmv   (any file named "nuXmv")
#      MATIEC_IEC2C-> exactly           $HOME/matiec/iec2c
#
#    nuXmv 2.2.0 (Linux 64-bit) is bundled as toolchain/nuXmv.tar.xz:
mkdir -p ~/nuxmv && tar -xJf toolchain/nuXmv.tar.xz -C ~/nuxmv
#      (archive layout: nuXmv-2.2.0-linux64/usr/local/bin/nuXmv - the script finds it by name)
#
#    MATIEC (iec2c, ST->C compiler) is built from source:
sudo apt-get install -y build-essential flex bison autoconf
#      then build per toolchain/wsl_build_matiec.sh from toolchain/matiec_src.tar.gz, and
#      place/symlink the resulting binary at ~/matiec/iec2c
```

### Sanity checks before the big run
```bash
python -c "import torch; x=torch.randn(8,8,device='cuda'); print((x@x).sum().item())"  # GPU live
PYTHONPATH=$PWD python analysis/test_gated_reward.py     # gated-reward logic (CPU, no oracle) -> exit 0
echo "$NUXMV_BIN"; "$MATIEC_IEC2C" --help >/dev/null 2>&1 && echo matiec-ok    # oracle present
```

The base model `Qwen/Qwen2.5-Coder-7B-Instruct` downloads from Hugging Face on first use
(set `HF_HOME` if you want to control the cache location; the script defaults it to
`$HOME/.hf_home`).

Box gotchas already handled in code - do NOT re-fix: `finetune/rl.py` sets
`torch.backends.cudnn.enabled=False` and `attn_implementation="eager"`; scripts target
trl ≥ 1.7 / transformers 5.x.

---

## 2. The single command to run

```bash
bash toolchain/run_vm_gated.sh            # seeds 0 1 2 (default); or pass explicit seeds
```

It is **idempotent** - each adapter/eval is skipped if its output already exists, so it is
safe to re-run after an interruption. Live progress: `results/exp_gated/STATUS.log`.
For an unattended run:
`setsid bash toolchain/run_vm_gated.sh > results/exp_gated/run.out 2>&1 &`.

Per seed S ∈ {0,1,2} it: (1) trains `finetune.rl --reward taskvalid_gated` from
`finetune/out/full/sftlite_s$S` on `finetune/data/rl_prompts_taskvalid.jsonl`
(num_gen 8, grad_accum 4, temperature 1.0, **STEPS=50**) → adapter
`finetune/out/gated/rlgated_sftlite_s$S`; (2) runs `analysis.eval_full --n 10 --k 1,3,5,10
--temperature 0.8` on all 22 tasks, saving every raw sample →
`results/exp_gated/rlgated_sftlite_s$S.json`; (3) aggregates the 3 seeds →
`results/exp_gated/gated_summary.json`.

> Step count: the shipped script has `STEPS=50` at the top (matches the Exp1b RL-func run for
> an exactly comparable row). `docs/14_VM_PLAN.md` discusses a 30-step variant; if you want
> 30, edit `STEPS=30` at the top of `toolchain/run_vm_gated.sh`. This README documents the
> script as shipped (50).

---

## 3. Expected wall-clock time

- Environment setup (venv + pip cu128 + MATIEC build + nuXmv untar + first HF model
  download): roughly **30-50 min**, dominated by the torch/cu128 download and the ~15 GB
  model pull.
- GPU run at **STEPS=50**: **~2.2-2.5 GPU-hours** for all 3 seeds
  (train ≈ 38 min/seed + eval ≈ 6 min/seed + model load/quantize overhead).
  (At STEPS=30 it drops to ~1.5-2 GPU-hours.)
- **Total: budget ~3-3.5 wall-clock hours** on a fresh 5090 box. Stop/destroy the instance
  the moment `results/exp_gated/STATUS.log` prints `DONE`.

---

## 4. What to copy BACK after the run

The entire output directory **`results/exp_gated/`**, specifically:
- `results/exp_gated/rlgated_sftlite_s{0,1,2}.json` - per-seed task-valid pass@k WITH raw
  samples (`rows[].samples[].code`), so everything downstream is recomputable offline.
- `results/exp_gated/gated_summary.json` - mean±std pass@k + bootstrap CI.
- `results/exp_gated/metrics_sftlite_s{0,1,2}.json` - per-step GRPO diagnostics.
- `results/exp_gated/STATUS.log` + `logs_*.log`.
- Optional: the trained adapters `finetune/out/gated/rlgated_sftlite_s{0,1,2}/` (small LoRAs)
  if you want to re-eval later.

The paired diff vs the ungated RL-func run (what the critical gate costs/gains) is computed
offline on CPU afterwards - see `docs/14_VM_PLAN.md` §5.

---

## 5. DO-NOT-RECOMPUTE manifest (results/ already contains these - never re-run)

| results/ path | what it holds |
|---|---|
| `exp1a/` | SFT-lite eval (task-valid pass@k, raw samples), seeds - the gated run's warm-start baseline |
| `exp1b/` | Exp1b RL-func (`rlfunc_sftlite`) eval - the ungated matched comparison to the gated run |
| `exp2/` | Data-composition ablations (dual / matiec_only / property_only / random / all) |
| `exp3/` | GRPO hyperparameter sweep (beta / entropy-reg variants) |
| `exp5/` | Repair-signal ablations (full / nocex / proponly / erroronly / shuffle / generic_sft) |
| `exp6/` | Functional-reward RL block results |
| `exp7/` | (run_exp7) results block |
| `frontier_n10/` | Frontier-model pass@k (n=10), API models |
| `frontier_n10_constrained/` | Frontier-model pass@k (n=10), constrained-prompt variant |
| `difftest/` | Differential-testing run (v1) |
| `difftest_v4/` | Differential-testing run (v4) |
| `full/` | Full-suite consolidated eval outputs |
| `seeds/` | Seed-sweep eval outputs |
| `v2/` | SFT-v2 sweep eval outputs |
| `matched_seeds.json` | Seed-matching manifest across stages |
| `t1s_boundary_audit.json` | T1S boundary-condition audit |
| `scenario_stats.json`, `taskvalid.json`, `vacuity.json`, `mutation.json`, `degenerate_rewards.json` | Oracle/reward integrity + benchmark-validity audits |
| `baselines.json`, `reference.json` | Baseline + reference-solution verification |
| `{openai_gpt-4o,anthropic_claude-sonnet-4-6,gemini_gemini-2.5-flash,grok_grok-3}.json` | Per-provider frontier eval outputs |
| `passk_*.json` | Cached pass@k summaries (per provider, nuxmv-only, and hf base/sft/rl) |
| `logs_*.log`, `train_STATUS.log` | Training/eval run logs (evidence) |

The ONLY new directory this VM job creates is `results/exp_gated/` (§4). Everything above is
finished evidence - do not repeat it.
