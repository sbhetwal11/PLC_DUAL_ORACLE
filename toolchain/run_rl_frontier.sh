#!/usr/bin/env bash
# Corrected v2 RL: verifier-reward GRPO from the BASE policy (high entropy -> reward
# variance) on base-selected held-out hard FRONTIER prompts, across seeds, then eval.
# Requires finetune/data/rl_prompts.jsonl (from finetune.select_rl_prompts probing the
# base model with --only-hard). Writes results/v2/rlbase_s<seed>.json.
# Usage: bash toolchain/run_rl_frontier.sh [seeds...]   (default 0 1 2)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
PY="$HOME/plcvenv/bin/python"; MODEL="Qwen/Qwen2.5-Coder-7B-Instruct"
RLP="finetune/data/rl_prompts.jsonl"; N=10; KS="1,3,5,10"; TEMP=0.8
if [ "$#" -gt 0 ]; then SEEDS=("$@"); else SEEDS=(0 1 2); fi
LOGD="$REPO/results/v2/logs"; mkdir -p results/v2 "$LOGD"
ts(){ date -u +%H:%M:%S; }
for S in "${SEEDS[@]}"; do
  echo "[$(ts)] === seed $S: RL-from-base train (frontier prompts)"
  $PY -m finetune.rl --data "$RLP" --model "$MODEL" --adapter none \
      --out "finetune/out/v2/rlbase_s$S" --num_gen 8 --grad_accum 4 \
      --max_steps 50 --seed $S > "$LOGD/rlbase_train_s$S.log" 2>&1
  echo "[$(ts)] seed $S: RL-from-base eval"
  $PY -m plcbench.cli eval-passk --model "hf:$MODEL+finetune/out/v2/rlbase_s$S" \
      --n $N --k $KS --temperature $TEMP --seed $S \
      --out "results/v2/rlbase_s$S.json" > "$LOGD/rlbase_eval_s$S.log" 2>&1
  rm -rf "finetune/out/v2/rlbase_s$S"/checkpoint-* 2>/dev/null
  echo "[$(ts)] seed $S done"
done
echo "[$(ts)] RL-FRONTIER DONE: seeds ${SEEDS[*]}"
