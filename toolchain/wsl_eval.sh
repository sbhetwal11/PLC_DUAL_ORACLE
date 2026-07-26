#!/usr/bin/env bash
# Run the Phase-C LLM evaluation in WSL with nuXmv as the verifier.
# Usage: wsl_eval.sh [model_spec]   (default: reference)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${1:-reference}"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
[ -x "$HOME/matiec/iec2c" ] && export MATIEC_IEC2C="$HOME/matiec/iec2c"
PYBIN="$HOME/plcvenv/bin/python"
[ -x "$PYBIN" ] || PYBIN=python3
cd "$REPO"
echo "model=$MODEL  NUXMV_BIN=$NUXMV_BIN"
PYTHONPATH="$REPO" "$PYBIN" -m plcbench.cli eval-llm --model "$MODEL" \
    --out "results/${MODEL//[:\/]/_}.json"
