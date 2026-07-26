#!/usr/bin/env bash
# Exp1(a) + scaling: task-valid pass@k of EXISTING trained adapters (INFERENCE only).
# Saves raw programs (n=10) via analysis.eval_full so task-valid, output-activity
# (Exp8) and best-of-k (Exp7) can all be computed offline. Idempotent: skips outputs
# that already exist. Reuses prior adapters -- NO retraining here.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-$HOME/.hf_home}"
PY="$HOME/plcvenv/bin/python"
M7="Qwen/Qwen2.5-Coder-7B-Instruct"
OUT="results/exp1a"; LOGD="$OUT/logs"; mkdir -p "$OUT" "$LOGD"
STATUS="$OUT/STATUS.log"
ts(){ date -u +%H:%M:%SZ; }
say(){ echo "[$(ts)] $*" | tee -a "$STATUS"; }
ev(){ # stage adapterspec seed
  local stage="$1" spec="$2" seed="$3" out="$OUT/${1}_s${3}.json"
  if [ -s "$out" ]; then say "skip $stage s$seed (exists)"; return; fi
  say "START $stage s$seed"
  if $PY -m analysis.eval_full --model "$spec" --n 10 --k 1,3,5,10 --temperature 0.8 \
        --seed "$seed" --out "$out" > "$LOGD/${stage}_s${seed}.log" 2>&1; then
    say "OK    $stage s$seed  $(grep -o '\"taskvalid_pass@1\": [0-9.]*' "$out" | head -1)"
  else say "FAIL  $stage s$seed (see $LOGD/${stage}_s${seed}.log)"; fi
}

say "===== EXP1a 7B inference sweep ====="
for S in 0 1 2; do
  ev base   "hf:$M7"                              $S
  ev sft    "hf:$M7+finetune/out/seeds/sft_s$S"   $S
  ev rl     "hf:$M7+finetune/out/seeds/rl_s$S"    $S
  ev sftv2  "hf:$M7+finetune/out/v2/sft_s$S"      $S
  ev sftlite "hf:$M7+finetune/out/full/sftlite_s$S" $S
  ev rllite  "hf:$M7+finetune/out/full/rllite_s$S"  $S
  ev rlbase  "hf:$M7+finetune/out/v2/rlbase_s$S"    $S
  ev sftzs   "hf:$M7+finetune/out/full/sftzs_s$S"   $S
done
say "===== EXP1a 7B DONE ====="
