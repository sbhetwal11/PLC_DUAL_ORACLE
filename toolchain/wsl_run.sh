#!/usr/bin/env bash
# Run the harness end-to-end in WSL with nuXmv as the verifier.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NUXMV_BIN="$(find "$HOME/nuxmv" -type f -name nuXmv | head -n1)"
[ -x "$HOME/matiec/iec2c" ] && export MATIEC_IEC2C="$HOME/matiec/iec2c"

# ensure pydantic (prefer a venv; fall back to user install)
PYBIN=python3
if ! python3 -c "import pydantic" 2>/dev/null; then
  if python3 -m venv "$HOME/plcvenv" 2>/dev/null; then
    "$HOME/plcvenv/bin/pip" -q install pydantic >/dev/null 2>&1
    PYBIN="$HOME/plcvenv/bin/python"
  else
    pip3 install --user --break-system-packages -q pydantic >/dev/null 2>&1
  fi
fi
echo "PYBIN=$PYBIN ; NUXMV_BIN=$NUXMV_BIN"
cd "$REPO"

echo "===== check-tools ====="
PYTHONPATH="$REPO" "$PYBIN" -m plcbench.cli check-tools

echo "===== run (references; expect verify=OK) ====="
PYTHONPATH="$REPO" "$PYBIN" -m plcbench.cli run

echo "===== negative control: buggy E01 (ignores EStop) ====="
PYTHONPATH="$REPO" "$PYBIN" - <<'PY'
from plcbench.loader import load_all
from plcbench.backends.verify_nuxmv import verify
lt = next(x for x in load_all() if x.id == "E01_motor_interlock")
buggy = """PROGRAM motor_interlock
VAR_INPUT Start:BOOL; Stop:BOOL; EStop:BOOL; END_VAR
VAR_OUTPUT Motor:BOOL; END_VAR
IF Stop THEN Motor:=FALSE; ELSIF Start THEN Motor:=TRUE; END_IF;
END_PROGRAM"""
res = verify(lt.task, buggy)
for p in res.properties:
    print(f"  {p.property_id}: {p.status}")
    if p.status == "fail" and p.counterexample:
        head = p.counterexample.splitlines()[:6]
        print("    CEX> " + "\n    CEX> ".join(head))
PY
