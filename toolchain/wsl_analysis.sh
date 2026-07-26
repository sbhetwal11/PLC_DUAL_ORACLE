#!/usr/bin/env bash
# Run a local CPU-only analysis script under the WSL harness (nuXmv + MATIEC).
# Usage: wsl_analysis.sh <python-script-relative-to-repo> [args...]
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv 2>/dev/null | head -n1)"
[ -x "$HOME/matiec/iec2c" ] && export MATIEC_IEC2C="$HOME/matiec/iec2c"
PYBIN="$HOME/plcvenv/bin/python"
[ -x "$PYBIN" ] || PYBIN=python3
cd "$REPO"
echo "REPO=$REPO"
echo "NUXMV_BIN=$NUXMV_BIN"
echo "MATIEC_IEC2C=${MATIEC_IEC2C:-<unset>}"
echo "PYBIN=$PYBIN"
echo "----"
SCRIPT="$1"; shift
PYTHONPATH="$REPO" "$PYBIN" "$SCRIPT" "$@"
