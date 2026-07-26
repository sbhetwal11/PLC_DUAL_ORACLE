#!/usr/bin/env bash
# Resume ONLY the 14B pipeline (EXP2b) after a teardown. Idempotent: each step is
# skipped if its output already exists, so it is safe to re-run repeatedly.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
export MATIEC_IEC2C="$HOME/matiec/iec2c"
export PYTHONPATH="$REPO"; export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-/workspace/.hf_home}"
export PLCBENCH_LOAD_4BIT=1
PY="$HOME/plcvenv/bin/python"; M14="Qwen/Qwen2.5-Coder-14B-Instruct"
DATA="finetune/data/sft.jsonl"; N=10; KS="1,3,5,10"; TEMP=0.8
OUT="results/full"; AD="finetune/out/full"; LOGD="$OUT/logs"; STATUS="$OUT/STATUS.log"
ts(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
say(){ echo "[$(ts)] $*" | tee -a "$STATUS"; }
step(){ local name="$1"; shift; say "START $name"; if "$@" >"$LOGD/$name.log" 2>&1; then say "OK    $name"; else say "FAIL  $name"; fi; }
evalpk(){ $PY -m plcbench.cli eval-passk --model "$1" --n $N --k $KS --temperature $TEMP --seed "$2" --out "$3"; }
prune(){ rm -rf "$1"/checkpoint-* 2>/dev/null || true; }
has_json(){ [ -s "$1" ]; }
has_adapter(){ [ -f "$1/adapter_model.safetensors" ]; }

say "======= EXP2b 14B RESUME ======="
for S in 0 1 2; do
  has_json "$OUT/base_14b_s$S.json" || step "exp2b_base_eval_s$S" evalpk "hf:$M14" $S "$OUT/base_14b_s$S.json"
  has_adapter "$AD/sft_14b_s$S" || step "exp2b_sft_train_s$S" $PY -m finetune.sft --data "$DATA" --model "$M14" --out "$AD/sft_14b_s$S" --seed $S
  has_json "$OUT/sft_14b_s$S.json" || step "exp2b_sft_eval_s$S" evalpk "hf:$M14+$AD/sft_14b_s$S" $S "$OUT/sft_14b_s$S.json"
  has_adapter "$AD/rl_14b_s$S" || step "exp2b_rl_train_s$S" $PY -m finetune.rl --data "$DATA" --model "$M14" \
       --adapter "$AD/sft_14b_s$S" --out "$AD/rl_14b_s$S" --num_gen 6 --grad_accum 4 --max_steps 30 --max_completion_length 384 --seed $S
  has_json "$OUT/rl_14b_s$S.json" || step "exp2b_rl_eval_s$S" evalpk "hf:$M14+$AD/rl_14b_s$S" $S "$OUT/rl_14b_s$S.json"
  prune "$AD/sft_14b_s$S"; prune "$AD/rl_14b_s$S"
done
$PY -m finetune.aggregate_seeds --dir "$OUT" --stages base_14b,sft_14b,rl_14b --seeds 0,1,2 --out "$OUT/exp2b_summary.json" >>"$LOGD/aggregate.log" 2>&1 || true
say "======= EXP2b 14B RESUME DONE ======="
