#!/usr/bin/env bash
# Run the Phase-C eval for several models (sources keys from ~/.plcbench_env).
# Usage: wsl_eval_all.sh [model_spec ...]   (defaults to the four baselines)
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$HOME/.plcbench_env" ] && source "$HOME/.plcbench_env"

MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  MODELS=(anthropic:claude-sonnet-4-6 openai:gpt-4o gemini:gemini-2.5-flash grok:grok-3)
fi

for m in "${MODELS[@]}"; do
  echo "====MODEL $m===="
  bash "$REPO/toolchain/wsl_eval.sh" "$m"
done
