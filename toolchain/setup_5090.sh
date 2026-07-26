#!/usr/bin/env bash
# One-command setup on the 5090 (or any Linux box / WSL): builds the CPU toolchain
# (MATIEC + nuXmv from the bundled tarballs -- no downloads) and a Python venv with
# the harness deps. GPU training deps (torch cu128 + trl/peft/...) are installed
# separately (see the printed next steps), because torch needs a special index.
set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "== apt build deps =="
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq flex bison autoconf automake build-essential \
    python3 python3-venv python3-pip xz-utils git

echo "== nuXmv (from bundled toolchain/nuXmv.tar.xz) =="
mkdir -p "$HOME/nuxmv"
tar -xf "$REPO/toolchain/nuXmv.tar.xz" -C "$HOME/nuxmv" --strip-components=1

echo "== MATIEC (build from bundled toolchain/matiec_src.tar.gz) =="
bash "$REPO/toolchain/wsl_build_matiec_local.sh"

echo "== python venv + harness deps =="
python3 -m venv "$HOME/plcvenv"
"$HOME/plcvenv/bin/pip" install -q --upgrade pip
"$HOME/plcvenv/bin/pip" install -q pydantic pytest

echo
echo "DONE."
echo "  nuXmv : $(find "$HOME/nuxmv" -name nuXmv -type f | head -1)"
echo "  matiec: $HOME/matiec/iec2c"
echo "  venv  : $HOME/plcvenv"
echo
echo "Next:"
echo "  1) GPU training deps:"
echo "       $HOME/plcvenv/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128"
echo "       $HOME/plcvenv/bin/pip install -r $REPO/finetune/requirements.txt"
echo "  2) export API keys for frontier baselines (e.g. ANTHROPIC_API_KEY=...)"
echo "  3) sanity-check the harness:  bash $REPO/toolchain/wsl_run.sh   (expect 22/22)"
echo "  4) pipeline:                  see $REPO/finetune/README.md"
