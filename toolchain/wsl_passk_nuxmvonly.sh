#!/usr/bin/env bash
# pass@k WITHOUT the compiler oracle (nuXmv-only) -> for the exact same-n
# safety-only vs dual-oracle (compile+verify) comparison (paper RQ2).
# Writes results/passk_nuxmvonly_<model>.json.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$HOME/.plcbench_env" ] && source "$HOME/.plcbench_env"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
unset MATIEC_IEC2C                # disable the compiler oracle for this run
PYBIN="$HOME/plcvenv/bin/python"; [ -x "$PYBIN" ] || PYBIN=python3
cd "$REPO"
N="${1:-10}"; K="${2:-1,3,5,10}"
MODELS=(anthropic:claude-sonnet-4-6 openai:gpt-4o gemini:gemini-2.5-flash grok:grok-3)
for m in "${MODELS[@]}"; do
  echo "====PASSK-NUXMVONLY $m (n=$N k=$K)===="
  PYTHONPATH="$REPO" "$PYBIN" -m plcbench.cli eval-passk --model "$m" \
      --n "$N" --k "$K" --temperature 0.8 \
      --out "results/passk_nuxmvonly_${m//[:\/]/_}.json"
done
echo "ALL NUXMVONLY DONE"
