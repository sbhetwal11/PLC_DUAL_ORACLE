#!/usr/bin/env bash
# Extract nuXmv into WSL, sanity-check it, and report the Python env.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TB="$REPO/toolchain/nuXmv.tar.xz"
DEST="$HOME/nuxmv"

echo "== extract nuXmv =="
mkdir -p "$DEST"
tar -xf "$TB" -C "$DEST" --strip-components=1
NUXMV="$(find "$DEST" -type f -name nuXmv 2>/dev/null | head -n1)"
chmod +x "$NUXMV" 2>/dev/null || true
echo "NUXMV=$NUXMV"

echo "== nuXmv sanity =="
"$NUXMV" -help 2>&1 | head -n 3

echo "== python in WSL =="
python3 --version 2>&1 || echo "no python3"
python3 -c "import pydantic; print('pydantic', pydantic.VERSION)" 2>/dev/null || echo "pydantic MISSING"
command -v pip3 >/dev/null && echo "pip3 present" || echo "pip3 MISSING"
