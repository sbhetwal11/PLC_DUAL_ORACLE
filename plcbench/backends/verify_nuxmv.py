"""Formal verification backend (nuXmv).

Translates the candidate ST to an SMV model (plcbench.st.smv), then checks each
SafetyProperty with nuXmv - one property per invocation so counterexamples map
unambiguously to a property (the CEX is the Phase-C repair/reward signal).

Runs end-to-end once nuXmv is on PATH or $NUXMV_BIN is set; otherwise returns
'unavailable' results so the harness still works on a bare machine.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..schema import Task
from ..st import STSyntaxError
from ..st.parser import parse_program
from ..st.smv import SMVTranslateError, model_smv, spec_line
from . import PropertyResult, VerifyResult

NUXMV = os.environ.get("NUXMV_BIN") or shutil.which("nuXmv") or shutil.which("nuxmv")


def nuxmv_available() -> bool:
    return NUXMV is not None


def verify(task: Task, st_code: str) -> VerifyResult:
    if not nuxmv_available():
        return _all(task, "unavailable",
                    "nuXmv not installed (build toolchain/Dockerfile, or set NUXMV_BIN)")

    # Translate once; a parse/translate failure fails every property (bad code).
    try:
        prog = parse_program(st_code)
        model = model_smv(prog, task)
    except (STSyntaxError, SMVTranslateError) as e:
        return _all(task, "error", f"translation failed: {e}")

    props = []
    for p in task.safety_properties:
        smv = model + "\n" + spec_line(p) + "\n"
        status, cex, detail = _run_one(smv)
        props.append(PropertyResult(property_id=p.id, status=status, tool="nuXmv",
                                     counterexample=cex, detail=detail))
    return VerifyResult(tool="nuXmv", available=True, properties=props)


def _all(task: Task, status: str, detail: str) -> VerifyResult:
    return VerifyResult(
        tool="nuXmv", available=(status != "unavailable"),
        properties=[PropertyResult(property_id=p.id, status=status, tool="nuXmv",
                                   detail=detail) for p in task.safety_properties],
    )


_TRUE = re.compile(r"specification .* is true", re.IGNORECASE)
_FALSE = re.compile(r"specification .* is false", re.IGNORECASE)


def _run_one(smv_text: str):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "m.smv"
        f.write_text(smv_text, encoding="utf-8")
        try:
            p = subprocess.run([NUXMV, str(f)], capture_output=True, text=True,
                               errors="replace", timeout=120)
        except subprocess.TimeoutExpired:
            return "unknown", "", "nuXmv timeout"
        out = p.stdout + "\n" + p.stderr
        if _FALSE.search(out):
            return "fail", _extract_cex(out), ""
        if _TRUE.search(out):
            return "pass", "", ""
        return "error", "", out.strip()[-400:]  # surface nuXmv parse/other errors


def _extract_cex(out: str) -> str:
    # capture the counterexample trace block nuXmv prints after 'is false'
    lines = out.splitlines()
    start = next((i for i, ln in enumerate(lines) if _FALSE.search(ln)), None)
    if start is None:
        return ""
    return "\n".join(lines[start:start + 60]).strip()
