#!/usr/bin/env bash
# NEW GPU training for the 8 DeepReview experiments. Reuses existing adapters where
# possible (Exp1a/7/8 are inference-only and NOT here). Idempotent: every step skips
# if its output already exists, so the script is safe to re-run after an interruption.
# Ordered by reviewer priority so the most important results land first.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-$HOME/.hf_home}"
PY="$HOME/plcvenv/bin/python"
M7="Qwen/Qwen2.5-Coder-7B-Instruct"
AD="finetune/out/exp"; mkdir -p "$AD"
STATUS="results/train_STATUS.log"; mkdir -p results
ts(){ date -u +%H:%M:%SZ; }
say(){ echo "[$(ts)] $*" | tee -a "$STATUS"; }
run(){ local name="$1"; shift; say "START $name"
  if "$@" > "results/logs_$name.log" 2>&1; then say "OK    $name"; else say "FAIL  $name"; fi; }
prune(){ rm -rf "$1"/checkpoint-* 2>/dev/null || true; }
evalf(){ # stage adapterspec seed outdir
  local out="$4/${1}_s${3}.json"
  [ -s "$out" ] && { say "skip eval $1 s$3"; return; }
  run "eval_${1}_s$3" $PY -m analysis.eval_full --model "$2" --n 10 --k 1,3,5,10 \
      --temperature 0.8 --seed "$3" --out "$out"
}

say "################ NEW TRAINING START ################"
# Serialize on the single GPU: wait for the Exp1a inference sweep to finish first.
if pgrep -f run_exp1a.sh >/dev/null 2>&1; then
  say "waiting for Exp1a inference sweep to release the GPU..."
  while pgrep -f run_exp1a.sh >/dev/null 2>&1; do sleep 60; done
  say "Exp1a done; starting training."
fi

########################################################################
# EXP1b + EXP6 - functional-reward RL on a FIXED frontier set, warm-started from
# {base, 3-epoch SFT, entropy-preserving SFT-lite}. Reward = TASK-VALID (compile +
# invariants + scenarios). Same fixed prompt set / rollout budget / #updates for all
# => Exp6 controlled comparison; the sftlite row is the Exp1b headline.
########################################################################
mkdir -p results/exp1b results/exp6
# Select ONE fixed functional frontier set under the TASK-VALID reward, probing the
# entropy-preserving SFT-lite policy (7B). This is the single fixed set used for ALL
# warm-starts below (M20). Fall back to the invariant-reward lite frontier if sparse.
RLP="finetune/data/rl_prompts_taskvalid.jsonl"
if [ ! -s "$RLP" ]; then
  run "exp1_select_frontier" $PY -m finetune.select_rl_prompts \
      --model "hf:$M7+finetune/out/full/sftlite_s0" --only-hard --reward taskvalid \
      --n 6 --keep 64 --min-std 0.05 --seed 0 --out "$RLP"
fi
if [ ! -s "$RLP" ] || [ "$(wc -l < "$RLP" 2>/dev/null || echo 0)" -lt 8 ]; then
  say "NOTE functional frontier sparse; using invariant-reward lite set with scenarios"
  RLP="finetune/data/rl_prompts_lite_func.jsonl"
fi
say "RL fixed frontier set = $RLP ($(wc -l < "$RLP" 2>/dev/null) prompts)"
for S in 0 1 2; do
  # sftlite warm-start (Exp1b headline)
  if [ ! -d "$AD/rlfunc_sftlite_s$S" ]; then
    run "rlfunc_sftlite_s$S" $PY -m finetune.rl --data "$RLP" --model "$M7" \
        --adapter "finetune/out/full/sftlite_s$S" --reward taskvalid \
        --out "$AD/rlfunc_sftlite_s$S" --num_gen 8 --grad_accum 4 --max_steps 50 \
        --temperature 1.0 --seed $S --metrics_out "results/exp6/metrics_sftlite_s$S.json"
    prune "$AD/rlfunc_sftlite_s$S"
  fi
  evalf rlfunc_sftlite "hf:$M7+$AD/rlfunc_sftlite_s$S" $S results/exp1b
  # base warm-start (Exp6 control)
  if [ ! -d "$AD/rlfunc_base_s$S" ]; then
    run "rlfunc_base_s$S" $PY -m finetune.rl --data "$RLP" --model "$M7" \
        --adapter base --reward taskvalid --out "$AD/rlfunc_base_s$S" \
        --num_gen 8 --grad_accum 4 --max_steps 50 --temperature 1.0 --seed $S \
        --metrics_out "results/exp6/metrics_base_s$S.json"
    prune "$AD/rlfunc_base_s$S"
  fi
  evalf rlfunc_base "hf:$M7+$AD/rlfunc_base_s$S" $S results/exp6
  # 3-epoch (low-entropy) SFT warm-start (Exp6 control)
  if [ ! -d "$AD/rlfunc_sft_s$S" ]; then
    run "rlfunc_sft_s$S" $PY -m finetune.rl --data "$RLP" --model "$M7" \
        --adapter "finetune/out/seeds/sft_s$S" --reward taskvalid \
        --out "$AD/rlfunc_sft_s$S" --num_gen 8 --grad_accum 4 --max_steps 50 \
        --temperature 1.0 --seed $S --metrics_out "results/exp6/metrics_sft_s$S.json"
    prune "$AD/rlfunc_sft_s$S"
  fi
  evalf rlfunc_sft "hf:$M7+$AD/rlfunc_sft_s$S" $S results/exp6
done

########################################################################
# EXP2 - filtering ablation (B3). Model-sampled REJECTABLE pool from the base
# policy, then 5 matched SFT sets (all / matiec_only / property_only / dual /
# random_sizematched). 3-epoch SFT (canonical hyperparams), eval task-valid.
########################################################################
mkdir -p results/exp2
if [ ! -s finetune/data/pool_model.jsonl ]; then
  run "exp2_pool" $PY -m finetune.build_model_pool --model "hf:$M7" --k 4 \
      --seed 0 --out finetune/data/pool_model.jsonl
fi
if [ ! -d finetune/data/ablation_model ] || [ ! -s finetune/data/ablation_model/dual.jsonl ]; then
  run "exp2_datasets" $PY - <<PYEOF
import json
from finetune.build_pool import composition, make_ablation_datasets
rows=[json.loads(l) for l in open("finetune/data/pool_model.jsonl") if l.strip()]
comp=composition(rows); counts=make_ablation_datasets(rows,"finetune/data/ablation_model",seed=0)
json.dump({"composition":comp,"dataset_sizes":counts}, open("results/exp2/composition_model.json","w"), indent=1)
print("composition",comp); print("sizes",counts)
PYEOF
fi
for COND in dual matiec_only property_only all random_sizematched; do
  for S in 0 1 2; do
    A="$AD/abl_${COND}_s$S"
    if [ ! -d "$A" ]; then
      run "exp2_${COND}_s$S" $PY -m finetune.sft --data "finetune/data/ablation_model/${COND}.jsonl" \
          --model "$M7" --out "$A" --epochs 3 --lr 2e-4 --seed $S
      prune "$A"
    fi
    evalf "abl_${COND}" "hf:$M7+$A" $S results/exp2
  done
done

########################################################################
# EXP5 - repair controls (M19). SFT on each feedback variant + generic baseline;
# eval on HELD-OUT bug type (force_true). Trained on weaken_or+flip_compare only.
########################################################################
mkdir -p results/exp5
for COND in full nocex proponly erroronly shuffle generic_sft; do
  DS="finetune/data/repair_ctl/repair_${COND}.jsonl"
  [ "$COND" = generic_sft ] && DS="finetune/data/repair_ctl/generic_sft.jsonl"
  for S in 0 1 2; do
    A="$AD/rep_${COND}_s$S"
    if [ ! -d "$A" ]; then
      run "exp5_${COND}_s$S" $PY -m finetune.sft --data "$DS" --model "$M7" \
          --out "$A" --epochs 3 --lr 2e-4 --seed $S
      prune "$A"
    fi
    OUT="results/exp5/rep_${COND}_s$S.json"
    [ -s "$OUT" ] || run "exp5eval_${COND}_s$S" $PY -m finetune.eval_repair \
        --model "hf:$M7+$A" --set finetune/data/repair_eval_heldout.jsonl \
        --n 10 --k 1,3,5,10 --seed $S --out "$OUT"
  done
done
# base repair baseline (no training) on the held-out set
for S in 0 1 2; do
  OUT="results/exp5/rep_base_s$S.json"
  [ -s "$OUT" ] || run "exp5eval_base_s$S" $PY -m finetune.eval_repair \
      --model "hf:$M7" --set finetune/data/repair_eval_heldout.jsonl \
      --n 10 --k 1,3,5,10 --seed $S --out "$OUT"
done

########################################################################
# EXP3 - entropy causal diagnostics (M13). Same FIXED prompt set + warm-start;
# vary entropy regularization; log group reward variance, zero-variance fraction,
# nonzero-advantage fraction, policy entropy, coeffs. (metrics only, short runs)
########################################################################
mkdir -p results/exp3
# high-entropy warm-start (sftlite) vs low-entropy (3-epoch sft), matched prompts+reward
run "exp3_hi_ent0"   $PY -m finetune.rl --data "$RLP" --model "$M7" \
    --adapter finetune/out/full/sftlite_s0 --reward taskvalid --out "$AD/ent_hi_e0" \
    --max_steps 20 --num_gen 8 --grad_accum 4 --temperature 1.0 --seed 0 \
    --entropy_coef 0.0 --beta 0.0 --metrics_out results/exp3/hi_ent0.json
run "exp3_lo_ent0"   $PY -m finetune.rl --data "$RLP" --model "$M7" \
    --adapter finetune/out/seeds/sft_s0 --reward taskvalid --out "$AD/ent_lo_e0" \
    --max_steps 20 --num_gen 8 --grad_accum 4 --temperature 1.0 --seed 0 \
    --entropy_coef 0.0 --beta 0.0 --metrics_out results/exp3/lo_ent0.json
run "exp3_lo_entreg" $PY -m finetune.rl --data "$RLP" --model "$M7" \
    --adapter finetune/out/seeds/sft_s0 --reward taskvalid --out "$AD/ent_lo_ereg" \
    --max_steps 20 --num_gen 8 --grad_accum 4 --temperature 1.0 --seed 0 \
    --entropy_coef 0.05 --beta 0.0 --metrics_out results/exp3/lo_entreg.json
run "exp3_hi_beta"   $PY -m finetune.rl --data "$RLP" --model "$M7" \
    --adapter finetune/out/full/sftlite_s0 --reward taskvalid --out "$AD/ent_hi_beta" \
    --max_steps 20 --num_gen 8 --grad_accum 4 --temperature 1.0 --seed 0 \
    --entropy_coef 0.0 --beta 0.04 --metrics_out results/exp3/hi_beta.json
rm -rf "$AD"/ent_* 2>/dev/null || true

########################################################################
# EXP4 - 5 seeds for headline 7B (M16). Existing sftlite/rllite have seeds 0-2;
# train seeds 3,4. (rllite = frontier RL from sftlite on the invariant reward, to
# match the existing 3 seeds exactly.)
########################################################################
RLP_INV="finetune/data/rl_prompts_lite.jsonl"
for S in 3 4; do
  if [ ! -d "finetune/out/full/sftlite_s$S" ]; then
    run "exp4_sftlite_s$S" $PY -m finetune.sft --data finetune/data/sft.jsonl \
        --model "$M7" --out "finetune/out/full/sftlite_s$S" --epochs 1 --lr 1e-4 --seed $S
  fi
  evalf sftlite "hf:$M7+finetune/out/full/sftlite_s$S" $S results/exp1a
  if [ ! -d "finetune/out/full/rllite_s$S" ]; then
    run "exp4_rllite_s$S" $PY -m finetune.rl --data "$RLP_INV" --model "$M7" \
        --adapter "finetune/out/full/sftlite_s$S" --reward invariant \
        --out "finetune/out/full/rllite_s$S" --num_gen 8 --grad_accum 4 --max_steps 50 --seed $S
    prune "finetune/out/full/rllite_s$S"
  fi
  evalf rllite "hf:$M7+finetune/out/full/rllite_s$S" $S results/exp1a
  # base at seeds 3,4 for paired stats
  evalf base "hf:$M7" $S results/exp1a
done

say "################ NEW TRAINING DONE ################"
