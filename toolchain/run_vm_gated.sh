#!/usr/bin/env bash
# CRITICAL-PROPERTY HARD-GATED reward RL on the RTX 5090 (single VM job).
#
# Trains verifier-reward GRPO with the SAFETY-CRITICAL-GATED task-valid reward
# (finetune.reward.reward_taskvalid_gated / --reward taskvalid_gated) from the
# entropy-preserving SFT-lite warm-starts (seeds 0,1,2), then evaluates task-valid
# pass@k (n=10, temp 0.8) on all 22 benchmark tasks, SAVING every raw sample.
#
# Modeled exactly on the Exp1b/Exp6 functional-reward block of run_5090_train.sh:
#   same base model, same 39-prompt task-valid frontier set, same GRPO hyperparams
#   (num_gen 8, grad_accum 4, temperature 1.0, lr default 1e-5), same eval harness
#   (analysis.eval_full, n=10, k=1,3,5,10, temp 0.8). The ONLY differences vs Exp1b:
#     (1) --reward taskvalid_gated   (was: taskvalid)
#     (2) --max_steps 30             (Exp1b rlfunc_sftlite used 50; 30 requested for
#                                     this run -- see docs/14_VM_PLAN.md "step count").
#
# Env assumptions copied verbatim from the working box scripts (docs/11, docs/13):
#   cudnn disabled + eager attention are handled inside finetune/rl.py (torch.backends
#   .cudnn.enabled=False, attn_implementation="eager"); TRL 1.7 / transformers 5.x API.
#   nuXmv + MATIEC provide the reward oracle; venv at ~/plcvenv.
#
# Idempotent: each adapter/eval is skipped if its output already exists, so the
# script is safe to re-run after an interruption.
#
# Usage:  bash toolchain/run_vm_gated.sh [seeds...]      (default: 0 1 2)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-$HOME/.hf_home}"
PY="$HOME/plcvenv/bin/python"
M7="Qwen/Qwen2.5-Coder-7B-Instruct"
STEPS=50                         # see header + docs/14 (Exp1b used 50)
AD="finetune/out/gated"; mkdir -p "$AD"
OUTD="results/exp_gated"; mkdir -p "$OUTD"
STATUS="$OUTD/STATUS.log"
if [ "$#" -gt 0 ]; then SEEDS=("$@"); else SEEDS=(0 1 2); fi

ts(){ date -u +%H:%M:%SZ; }
say(){ echo "[$(ts)] $*" | tee -a "$STATUS"; }
run(){ local name="$1"; shift; say "START $name"
  if "$@" > "$OUTD/logs_$name.log" 2>&1; then say "OK    $name"; else say "FAIL  $name (see $OUTD/logs_$name.log)"; fi; }
prune(){ rm -rf "$1"/checkpoint-* 2>/dev/null || true; }

say "############ CRITICAL-GATED REWARD RL START ############"
say "NUXMV_BIN=$NUXMV_BIN  MATIEC_IEC2C=$MATIEC_IEC2C"
[ -x "$NUXMV_BIN" ] || say "WARN nuXmv not found -- the gated reward cannot verify; check \$HOME/nuxmv"
[ -f "$MATIEC_IEC2C" ] || say "WARN MATIEC iec2c not found at $MATIEC_IEC2C"

# The SAME fixed 39-prompt task-valid frontier set used by Exp1b (docs/13). It is
# committed in the repo; fall back to the invariant-reward lite+scenario set if absent.
RLP="finetune/data/rl_prompts_taskvalid.jsonl"
if [ ! -s "$RLP" ]; then
  say "NOTE $RLP missing; falling back to finetune/data/rl_prompts_lite_func.jsonl"
  RLP="finetune/data/rl_prompts_lite_func.jsonl"
fi
say "RL frontier set = $RLP ($(wc -l < "$RLP" 2>/dev/null || echo 0) prompts); steps=$STEPS"

for S in "${SEEDS[@]}"; do
  WARM="finetune/out/full/sftlite_s$S"
  if [ ! -d "$WARM" ]; then say "FAIL  missing warm-start adapter $WARM -- upload it (docs/14)"; continue; fi
  ADIR="$AD/rlgated_sftlite_s$S"
  if [ ! -d "$ADIR" ]; then
    run "rlgated_sftlite_s$S" $PY -m finetune.rl --data "$RLP" --model "$M7" \
        --adapter "$WARM" --reward taskvalid_gated --out "$ADIR" \
        --num_gen 8 --grad_accum 4 --max_steps "$STEPS" --temperature 1.0 --seed "$S" \
        --metrics_out "$OUTD/metrics_sftlite_s$S.json"
    prune "$ADIR"
  else
    say "skip train (exists) $ADIR"
  fi
  # task-valid pass@k eval on all 22 tasks, raw samples saved (analysis.eval_full)
  OUT="$OUTD/rlgated_sftlite_s$S.json"
  if [ -s "$OUT" ]; then say "skip eval (exists) $OUT"; else
    run "eval_rlgated_sftlite_s$S" $PY -m analysis.eval_full \
        --model "hf:$M7+$ADIR" --n 10 --k 1,3,5,10 --temperature 0.8 --seed "$S" --out "$OUT"
  fi
done

# Aggregate the 3 seeds with the SAME aggregator Exp1b used for eval_full outputs
# (analysis.aggregate_full: task-valid mean±std pass@k + hierarchical-bootstrap CI).
# To also get paired seed diffs vs the SFT-lite start and the Exp1b RL-func run, copy
# their eval JSONs (results/exp1a/sftlite_s*.json, results/exp1b/rlfunc_sftlite_s*.json)
# into "$OUTD" first and add them to --stages (see docs/14_VM_PLAN.md).
say "AGGREGATE (task-valid)"
$PY -m analysis.aggregate_full --dir "$OUTD" --stages rlgated_sftlite \
    --seeds "$(IFS=,; echo "${SEEDS[*]}")" --metric both \
    --out "$OUTD/gated_summary.json" \
    >> "$OUTD/logs_aggregate.log" 2>&1 || say "NOTE aggregate step failed (see logs_aggregate.log); raw per-seed JSONs are still usable"
say "############ CRITICAL-GATED REWARD RL DONE ############"
say "outputs: $OUTD/rlgated_sftlite_s{${SEEDS[*]}}.json (+ metrics_*, gated_summary.json)"
