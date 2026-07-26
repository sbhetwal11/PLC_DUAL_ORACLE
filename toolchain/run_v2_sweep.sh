#!/usr/bin/env bash
# Phase-3 v2: strengthened data (hard families + counterexample-repair pairs) and
# failure-frequency RL prompt selection, run across seeds.
#   build v2 data -> per-seed SFT_v2 + eval -> select RL prompts (once) ->
#   per-seed RL_v2 (on selected prompts) + eval.
# Writes pass@k JSONs to results/v2/ and logs to results/v2/logs/.
# Usage: bash toolchain/run_v2_sweep.sh [seeds...]   (default: 0 1 2)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
PY="$HOME/plcvenv/bin/python"
MODEL="Qwen/Qwen2.5-Coder-7B-Instruct"
DATA="finetune/data/sft_v2.jsonl"
RLP="finetune/data/rl_prompts.jsonl"
N=10; KS="1,3,5,10"; TEMP=0.8
if [ "$#" -gt 0 ]; then SEEDS=("$@"); else SEEDS=(0 1 2); fi
LOGD="$REPO/results/v2/logs"; mkdir -p results/v2 "$LOGD"
ts(){ date -u +%H:%M:%S; }

echo "[$(ts)] build v2 SFT data (hard families + repair pairs)"
$PY -m finetune.build_sft --include-hard --repair --out "$DATA" \
    > "$LOGD/build_v2.log" 2>&1
echo "[$(ts)] $(grep -E '^SFT:' "$LOGD/build_v2.log")"

for S in "${SEEDS[@]}"; do
  echo "[$(ts)] === seed $S: SFT_v2 train"
  $PY -m finetune.sft --data "$DATA" --model "$MODEL" \
      --out "finetune/out/v2/sft_s$S" --seed $S > "$LOGD/sft_train_s$S.log" 2>&1
  echo "[$(ts)] seed $S: SFT_v2 eval"
  $PY -m plcbench.cli eval-passk --model "hf:$MODEL+finetune/out/v2/sft_s$S" \
      --n $N --k $KS --temperature $TEMP --seed $S \
      --out "results/v2/sft_s$S.json" > "$LOGD/sft_eval_s$S.log" 2>&1
done

echo "[$(ts)] select RL frontier prompts once (from seed-0 SFT_v2)"
$PY -m finetune.select_rl_prompts --model "hf:$MODEL+finetune/out/v2/sft_s${SEEDS[0]}" \
    --n 5 --keep 64 --limit 120 --seed 0 --out "$RLP" > "$LOGD/select_prompts.log" 2>&1
echo "[$(ts)] $(grep -E '^selected' "$LOGD/select_prompts.log")"

for S in "${SEEDS[@]}"; do
  echo "[$(ts)] === seed $S: RL_v2 train (frontier prompts)"
  $PY -m finetune.rl --data "$RLP" --model "$MODEL" \
      --adapter "finetune/out/v2/sft_s$S" --out "finetune/out/v2/rl_s$S" \
      --num_gen 8 --grad_accum 4 --max_steps 40 --seed $S \
      > "$LOGD/rl_train_s$S.log" 2>&1
  echo "[$(ts)] seed $S: RL_v2 eval"
  $PY -m plcbench.cli eval-passk --model "hf:$MODEL+finetune/out/v2/rl_s$S" \
      --n $N --k $KS --temperature $TEMP --seed $S \
      --out "results/v2/rl_s$S.json" > "$LOGD/rl_eval_s$S.log" 2>&1
  rm -rf "finetune/out/v2/sft_s$S"/checkpoint-* "finetune/out/v2/rl_s$S"/checkpoint-* 2>/dev/null
done
echo "[$(ts)] V2 DONE: seeds ${SEEDS[*]}"
