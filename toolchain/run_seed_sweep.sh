#!/usr/bin/env bash
# 3-seed sweep: base -> SFT -> eval -> RL -> eval, per seed, with controlled seeds.
# Writes per-seed pass@k JSONs to results/seeds/ and logs to $LOGDIR.
# Usage: bash toolchain/run_seed_sweep.sh [seeds...]   (default: 0 1 2)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"
export TOKENIZERS_PARALLELISM=false
PY="$HOME/plcvenv/bin/python"
MODEL="Qwen/Qwen2.5-Coder-7B-Instruct"
DATA="finetune/data/sft.jsonl"
N=10; KS="1,3,5,10"; TEMP=0.8
if [ "$#" -gt 0 ]; then SEEDS=("$@"); else SEEDS=(0 1 2); fi
LOGDIR="${LOGDIR:-$REPO/results/seeds/logs}"
mkdir -p results/seeds "$LOGDIR"

ts() { date -u +%H:%M:%S; }
run() { echo "[$(ts)] >> $*"; "$@"; echo "[$(ts)] << exit=$?"; }

for S in "${SEEDS[@]}"; do
  echo "==================== SEED $S ===================="
  SFT_OUT="finetune/out/seeds/sft_s$S"
  RL_OUT="finetune/out/seeds/rl_s$S"

  echo "[$(ts)] base eval (seed $S)"
  $PY -m plcbench.cli eval-passk --model "hf:$MODEL" --n $N --k $KS \
      --temperature $TEMP --seed $S --out "results/seeds/base_s$S.json" \
      > "$LOGDIR/base_s$S.log" 2>&1

  echo "[$(ts)] SFT train (seed $S)"
  $PY -m finetune.sft --data "$DATA" --model "$MODEL" --out "$SFT_OUT" --seed $S \
      > "$LOGDIR/sft_train_s$S.log" 2>&1

  echo "[$(ts)] SFT eval (seed $S)"
  $PY -m plcbench.cli eval-passk --model "hf:$MODEL+$SFT_OUT" --n $N --k $KS \
      --temperature $TEMP --seed $S --out "results/seeds/sft_s$S.json" \
      > "$LOGDIR/sft_eval_s$S.log" 2>&1

  echo "[$(ts)] RL train (seed $S)"
  $PY -m finetune.rl --data "$DATA" --model "$MODEL" --adapter "$SFT_OUT" \
      --out "$RL_OUT" --num_gen 8 --grad_accum 4 --max_steps 30 --seed $S \
      > "$LOGDIR/rl_train_s$S.log" 2>&1

  echo "[$(ts)] RL eval (seed $S)"
  $PY -m plcbench.cli eval-passk --model "hf:$MODEL+$RL_OUT" --n $N --k $KS \
      --temperature $TEMP --seed $S --out "results/seeds/rl_s$S.json" \
      > "$LOGDIR/rl_eval_s$S.log" 2>&1

  # reclaim disk: drop intermediate checkpoints, keep the final adapters
  rm -rf "$SFT_OUT"/checkpoint-* "$RL_OUT"/checkpoint-* 2>/dev/null
  echo "[$(ts)] seed $S done"
done
echo "ALL SEEDS DONE: ${SEEDS[*]}"
