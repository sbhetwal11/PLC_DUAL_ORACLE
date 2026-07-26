#!/usr/bin/env bash
# Build MATIEC (iec2c) in WSL and test it on a reference solution.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== build deps =="
if command -v flex >/dev/null 2>&1 && command -v bison >/dev/null 2>&1 \
   && command -v autoreconf >/dev/null 2>&1; then
  echo "deps present (skipping apt)"
else
  sudo apt-get update -qq >/dev/null 2>&1
  sudo apt-get install -y -qq build-essential flex bison autoconf automake git >/dev/null 2>&1 \
    && echo "deps installed" \
    || echo "deps FAILED (run as root: apt-get install -y flex bison autoconf automake)"
fi

if [ ! -x "$HOME/matiec/iec2c" ]; then
  echo "== clone + build matiec =="
  rm -rf "$HOME/matiec"
  git clone --depth 1 https://github.com/nucleron/matiec "$HOME/matiec" >/dev/null 2>&1 \
    && echo "cloned" || echo "clone FAILED"
  ( cd "$HOME/matiec" && autoreconf -i >/dev/null 2>&1 && ./configure >/dev/null 2>&1 \
    && make -j"$(nproc)" >/dev/null 2>&1 ) && echo "built" || echo "build FAILED"
fi

if [ -x "$HOME/matiec/iec2c" ]; then echo "iec2c present"; else echo "iec2c MISSING"; fi

echo "== test iec2c on E01 reference =="
mkdir -p /tmp/mtest && cd /tmp/mtest
cp "$REPO/benchmark/tasks/easy/E01_motor_interlock/reference.st" /tmp/mtest/e01.st
"$HOME/matiec/iec2c" /tmp/mtest/e01.st; echo "iec2c exit: $?"
