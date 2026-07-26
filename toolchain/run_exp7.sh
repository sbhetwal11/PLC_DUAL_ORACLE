#!/usr/bin/env bash
# Exp7 (B7): inference-time verifier baselines (best-of-k + iterative counterexample
# repair) from the base and SFT policies, to compare against verifier-TRAINED policies
# at matched oracle budgets. Run AFTER the training master (serialize on the GPU).
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-$HOME/.hf_home}"
PY="$HOME/plcvenv/bin/python"; M7="Qwen/Qwen2.5-Coder-7B-Instruct"
OUT="results/exp7"; mkdir -p "$OUT"
say(){ echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$OUT/STATUS.log"; }
# wait for the training master to finish (GPU serialization)
while pgrep -f run_5090_train.sh >/dev/null 2>&1; do sleep 60; done
say "===== EXP7 inference baselines ====="
run(){ local o="$OUT/$1.json"; shift; [ -s "$o" ] && { say "skip $o"; return; }
  say "START $o"; if "$@" --out "$o" > "$OUT/logs_$(basename $o .json).log" 2>&1; then say "OK $o"; else say "FAIL $o"; fi; }
for S in 0 1 2; do
  run "base_infer_s$S"  $PY -m analysis.inference_baselines --model "hf:$M7" \
      --k 10 --repair 5 --seed $S
  run "sft_infer_s$S"   $PY -m analysis.inference_baselines \
      --model "hf:$M7+finetune/out/seeds/sft_s$S" --k 10 --repair 5 --seed $S
done
say "===== EXP7 DONE ====="
