#!/usr/bin/env bash
# pass@k evaluation for the four baseline models (keys from ~/.plcbench_env).
# Usage: wsl_passk_all.sh [N_samples] [k_csv]   (defaults: 5 samples, k=1,3,5)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$HOME/.plcbench_env" ] && source "$HOME/.plcbench_env"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
[ -x "$HOME/matiec/iec2c" ] && export MATIEC_IEC2C="$HOME/matiec/iec2c"
PYBIN="$HOME/plcvenv/bin/python"; [ -x "$PYBIN" ] || PYBIN=python3
cd "$REPO"
N="${1:-5}"; K="${2:-1,3,5}"
MODELS=(anthropic:claude-sonnet-4-6 openai:gpt-4o gemini:gemini-2.5-flash grok:grok-3)
for m in "${MODELS[@]}"; do
  echo "====PASSK $m (n=$N k=$K)===="
  PYTHONPATH="$REPO" "$PYBIN" -m plcbench.cli eval-passk --model "$m" \
      --n "$N" --k "$K" --temperature 0.8 \
      --out "results/passk_${m//[:\/]/_}.json"
done
echo "ALL PASSK DONE"
