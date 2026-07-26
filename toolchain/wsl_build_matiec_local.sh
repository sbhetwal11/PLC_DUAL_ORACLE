#!/usr/bin/env bash
# Build MATIEC from the local source tarball (toolchain/matiec_src.tar.gz),
# avoiding git (github git access is blocked from WSL here). Per-step timeouts +
# visible output so it cannot hang silently.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TB="$REPO/toolchain/matiec_src.tar.gz"
DEST="$HOME/matiec"

[ -f "$TB" ] || { echo "missing $TB"; exit 1; }
rm -rf "$DEST"; mkdir -p "$DEST"
tar -xzf "$TB" -C "$DEST" --strip-components=1
cd "$DEST" || exit 1

echo "== autoreconf =="; timeout 120 autoreconf -i 2>&1 | tail -3; echo "autoreconf_exit=${PIPESTATUS[0]}"
echo "== configure ==";  timeout 180 ./configure   2>&1 | tail -3; echo "configure_exit=${PIPESTATUS[0]}"
echo "== make ==";       timeout 300 make -j"$(nproc)" 2>&1 | tail -6; echo "make_exit=${PIPESTATUS[0]}"

if [ -x "$DEST/iec2c" ]; then
  echo "iec2c OK -> $DEST/iec2c"
else
  echo "iec2c MISSING"
fi
