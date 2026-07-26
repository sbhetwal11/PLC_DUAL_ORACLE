#!/usr/bin/env bash
# Phase-3 FULL SUITE - runs unattended end-to-end. Each experiment is independent
# (a failure logs and is skipped, the rest continue). Progress: results/full/STATUS.log.
#   EXP1  entropy-preserving SFT (1 epoch) -> frontier-RL, 7B, 3 seeds
#   EXP3  repair-pairs ablation (zeroshot-only SFT vs sft_v2), 7B, 3 seeds
#   EXP4  counterexample-guided REPAIR eval (base vs +repair vs -repair SFT)
#   EXP2a full base/SFT/RL pipeline on Qwen2.5-Coder-1.5B, 3 seeds
#   EXP2b full base/SFT/RL pipeline on Qwen2.5-Coder-14B (4-bit), 3 seeds
# 14B is last so everything cheaper finishes first.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-/workspace/.hf_home}"
PY="$HOME/plcvenv/bin/python"
M7="Qwen/Qwen2.5-Coder-7B-Instruct"
M1="Qwen/Qwen2.5-Coder-1.5B-Instruct"
M14="Qwen/Qwen2.5-Coder-14B-Instruct"
DATA="finetune/data/sft.jsonl"; N=10; KS="1,3,5,10"; TEMP=0.8
OUT="results/full"; AD="finetune/out/full"; LOGD="$OUT/logs"
mkdir -p "$OUT" "$AD" "$LOGD"
STATUS="$OUT/STATUS.log"
ts(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
say(){ echo "[$(ts)] $*" | tee -a "$STATUS"; }
# run a step; log START/OK/FAIL but never abort the suite
step(){ local name="$1"; shift; say "START $name"; if "$@" >"$LOGD/$name.log" 2>&1; then say "OK    $name"; else say "FAIL  $name (see $LOGD/$name.log)"; fi; }
evalpk(){ $PY -m plcbench.cli eval-passk --model "$1" --n $N --k $KS --temperature $TEMP --seed "$2" --out "$3"; }
prune(){ rm -rf "$1"/checkpoint-* 2>/dev/null || true; }

say "================ FULL SUITE START ================"

############################ EXP1 - entropy-preserving SFT -> frontier RL (7B) ##########
for S in 0 1 2; do
  step "exp1_sftlite_train_s$S" $PY -m finetune.sft --data "$DATA" --model "$M7" \
       --out "$AD/sftlite_s$S" --epochs 1 --lr 1e-4 --seed $S
  step "exp1_sftlite_eval_s$S"  evalpk "hf:$M7+$AD/sftlite_s$S" $S "$OUT/sftlite_s$S.json"
done
# frontier prompts from the (higher-entropy) lite SFT; fall back to base-probed set if sparse
step "exp1_select_prompts" $PY -m finetune.select_rl_prompts --model "hf:$M7+$AD/sftlite_s0" \
     --only-hard --n 6 --keep 64 --min-std 0.05 --seed 0 --out finetune/data/rl_prompts_lite.jsonl
RLP="finetune/data/rl_prompts_lite.jsonl"
if [ ! -s "$RLP" ] || [ "$(wc -l < "$RLP")" -lt 8 ]; then
  say "NOTE  lite-SFT frontier set sparse ($(wc -l < "$RLP" 2>/dev/null || echo 0)); using base-probed rl_prompts.jsonl"
  RLP="finetune/data/rl_prompts.jsonl"
fi
for S in 0 1 2; do
  step "exp1_rllite_train_s$S" $PY -m finetune.rl --data "$RLP" --model "$M7" \
       --adapter "$AD/sftlite_s$S" --out "$AD/rllite_s$S" --num_gen 8 --grad_accum 4 \
       --max_steps 50 --seed $S
  step "exp1_rllite_eval_s$S" evalpk "hf:$M7+$AD/rllite_s$S" $S "$OUT/rllite_s$S.json"
  prune "$AD/rllite_s$S"
done

############################ EXP3 - repair-pairs ablation (7B) ##########################
# zeroshot-only data (hard families, NO repair pairs); compare vs sft_v2 (zeroshot+repair)
step "exp3_build_zeroshot" $PY -m finetune.build_sft --include-hard \
     --out finetune/data/sft_zeroshot.jsonl
for S in 0 1 2; do
  step "exp3_sftzs_train_s$S" $PY -m finetune.sft --data finetune/data/sft_zeroshot.jsonl \
       --model "$M7" --out "$AD/sftzs_s$S" --seed $S
  step "exp3_sftzs_eval_s$S" evalpk "hf:$M7+$AD/sftzs_s$S" $S "$OUT/sftzs_s$S.json"
  prune "$AD/sftzs_s$S"
done

############################ EXP4 - counterexample-guided repair eval ###################
step "exp4_repair_build" $PY -m finetune.eval_repair --build
step "exp4_repair_base"  $PY -m finetune.eval_repair --model "hf:$M7" --n $N --k $KS --seed 0 --out "$OUT/repair_base.json"
# sft_v2 (trained WITH repair pairs) - adapter from the earlier v2 run
[ -d finetune/out/v2/sft_s0 ] && step "exp4_repair_sftv2" $PY -m finetune.eval_repair \
     --model "hf:$M7+finetune/out/v2/sft_s0" --n $N --k $KS --seed 0 --out "$OUT/repair_sftv2.json"
# zeroshot-only SFT (trained WITHOUT repair pairs) from EXP3
[ -d "$AD/sftzs_s0" ] && step "exp4_repair_sftzs" $PY -m finetune.eval_repair \
     --model "hf:$M7+$AD/sftzs_s0" --n $N --k $KS --seed 0 --out "$OUT/repair_sftzs.json"

############################ EXP2a - 1.5B full pipeline (3 seeds) #######################
for S in 0 1 2; do
  step "exp2a_base_eval_s$S" evalpk "hf:$M1" $S "$OUT/base_1p5b_s$S.json"
  step "exp2a_sft_train_s$S" $PY -m finetune.sft --data "$DATA" --model "$M1" --out "$AD/sft_1p5b_s$S" --seed $S
  step "exp2a_sft_eval_s$S"  evalpk "hf:$M1+$AD/sft_1p5b_s$S" $S "$OUT/sft_1p5b_s$S.json"
  step "exp2a_rl_train_s$S"  $PY -m finetune.rl --data "$DATA" --model "$M1" \
       --adapter "$AD/sft_1p5b_s$S" --out "$AD/rl_1p5b_s$S" --num_gen 8 --grad_accum 4 --max_steps 30 --seed $S
  step "exp2a_rl_eval_s$S"   evalpk "hf:$M1+$AD/rl_1p5b_s$S" $S "$OUT/rl_1p5b_s$S.json"
  prune "$AD/sft_1p5b_s$S"; prune "$AD/rl_1p5b_s$S"
done

############################ EXP2b - 14B full pipeline (3 seeds, 4-bit) #################
# free disk: the 7B (EXP1/3/4) and 1.5B (EXP2a) caches are no longer needed -> ~18 GB
# back, leaving room for the ~28 GB 14B download.
say "free HF cache before 14B: $(df -h / | awk 'NR==2{print $4}') free before"
rm -rf "$HF_HOME"/hub/models--Qwen--Qwen2.5-Coder-7B-Instruct \
       "$HF_HOME"/hub/models--Qwen--Qwen2.5-Coder-1.5B-Instruct 2>/dev/null || true
say "free HF cache before 14B: $(df -h / | awk 'NR==2{print $4}') free after"
export PLCBENCH_LOAD_4BIT=1     # load 14B in 4-bit for eval so it fits 32 GB
for S in 0 1 2; do
  step "exp2b_base_eval_s$S" evalpk "hf:$M14" $S "$OUT/base_14b_s$S.json"
  step "exp2b_sft_train_s$S" $PY -m finetune.sft --data "$DATA" --model "$M14" --out "$AD/sft_14b_s$S" --seed $S
  step "exp2b_sft_eval_s$S"  evalpk "hf:$M14+$AD/sft_14b_s$S" $S "$OUT/sft_14b_s$S.json"
  step "exp2b_rl_train_s$S"  $PY -m finetune.rl --data "$DATA" --model "$M14" \
       --adapter "$AD/sft_14b_s$S" --out "$AD/rl_14b_s$S" --num_gen 6 --grad_accum 4 \
       --max_steps 30 --max_completion_length 384 --seed $S
  step "exp2b_rl_eval_s$S"   evalpk "hf:$M14+$AD/rl_14b_s$S" $S "$OUT/rl_14b_s$S.json"
  prune "$AD/sft_14b_s$S"; prune "$AD/rl_14b_s$S"
done
unset PLCBENCH_LOAD_4BIT

############################ AGGREGATE ##################################################
say "AGGREGATE"
$PY -m finetune.aggregate_seeds --dir "$OUT" --stages sftlite,rllite --seeds 0,1,2 --out "$OUT/exp1_summary.json"   >>"$LOGD/aggregate.log" 2>&1 || true
$PY -m finetune.aggregate_seeds --dir "$OUT" --stages sftzs --seeds 0,1,2 --out "$OUT/exp3_summary.json"            >>"$LOGD/aggregate.log" 2>&1 || true
$PY -m finetune.aggregate_seeds --dir "$OUT" --stages base_1p5b,sft_1p5b,rl_1p5b --seeds 0,1,2 --out "$OUT/exp2a_summary.json" >>"$LOGD/aggregate.log" 2>&1 || true
$PY -m finetune.aggregate_seeds --dir "$OUT" --stages base_14b,sft_14b,rl_14b --seeds 0,1,2 --out "$OUT/exp2b_summary.json"    >>"$LOGD/aggregate.log" 2>&1 || true
say "================ FULL SUITE DONE ================"
