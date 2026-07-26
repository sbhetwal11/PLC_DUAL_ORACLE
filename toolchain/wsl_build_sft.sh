#!/usr/bin/env bash
# Build the SFT dataset with the dual oracle (MATIEC + nuXmv) in WSL.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
[ -x "$HOME/matiec/iec2c" ] && export MATIEC_IEC2C="$HOME/matiec/iec2c"
PYBIN="$HOME/plcvenv/bin/python"; [ -x "$PYBIN" ] || PYBIN=python3
cd "$REPO"
PYTHONPATH="$REPO" "$PYBIN" -m finetune.build_sft --out finetune/data/sft.jsonl
