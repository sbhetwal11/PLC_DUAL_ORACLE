"""ST compilation backend.

Primary: MATIEC (iec2c) - IEC 61131-3 -> C. Detected on PATH or via $MATIEC_IEC2C.
Fallback (no tools): a *very* lightweight structural syntax check so the harness
produces a signal on a bare laptop. The fallback is NOT a compiler and must never
be reported as one in the paper - it only checks block balancing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import CompileResult

IEC2C = os.environ.get("MATIEC_IEC2C") or shutil.which("iec2c")


def _lib_dir():
    # MATIEC needs its standard library dir via -I (env override or <iec2c>/../lib)
    lib = os.environ.get("MATIEC_LIB")
    if lib:
        return lib
    if IEC2C:
        cand = Path(IEC2C).parent / "lib"
        if cand.exists():
            return str(cand)
    return None


def matiec_available() -> bool:
    return IEC2C is not None and Path(IEC2C).exists()


def compile_st(st_code: str) -> CompileResult:
    if matiec_available():
        return _compile_with_matiec(st_code)
    res = _basic_syntax_check(st_code)
    res.available = False  # signal that the real compiler was not used
    return res


def _compile_with_matiec(st_code: str) -> CompileResult:
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "prog.st"
        src.write_text(st_code, encoding="utf-8")
        out = Path(td) / "out"
        out.mkdir()
        cmd = [IEC2C]
        lib = _lib_dir()
        if lib:
            cmd += ["-I", lib]
        cmd += ["-T", str(out), str(src)]
        try:
            p = subprocess.run(cmd, cwd=td, capture_output=True, text=True,
                               errors="replace", timeout=60)
        except subprocess.TimeoutExpired:
            return CompileResult(ok=False, tool="matiec", stderr="timeout")
        return CompileResult(
            ok=(p.returncode == 0), tool="matiec", stdout=p.stdout, stderr=p.stderr
        )


# --- fallback (placeholder only) -------------------------------------------
_PAIRS = [
    ("PROGRAM", "END_PROGRAM"),
    ("FUNCTION_BLOCK", "END_FUNCTION_BLOCK"),
    ("VAR", "END_VAR"),
    ("IF", "END_IF"),
    ("CASE", "END_CASE"),
    ("FOR", "END_FOR"),
    ("WHILE", "END_WHILE"),
]


def _strip_comments(st_code: str) -> str:
    import re

    # IEC 61131-3 block comments (* ... *) and line comments // ...
    s = re.sub(r"\(\*.*?\*\)", " ", st_code, flags=re.DOTALL)
    s = re.sub(r"//[^\n]*", " ", s)
    return s


def _basic_syntax_check(st_code: str) -> CompileResult:
    import re

    errs = []
    up = _strip_comments(st_code).upper()
    for open_kw, close_kw in _PAIRS:
        # word-boundary counts; END_VAR etc. are matched by their own pattern
        no = len(re.findall(rf"\b{open_kw}\b", up))
        nc = len(re.findall(rf"\b{close_kw}\b", up))
        # subtract close-keyword hits that also match the open pattern (e.g. END_IF contains IF? no, \b prevents)
        if open_kw == "VAR":
            # VAR also matches inside VAR_INPUT etc.; approximate, good enough for a lint
            no = len(re.findall(r"\bVAR(_INPUT|_OUTPUT|_IN_OUT|_GLOBAL|_TEMP)?\b", up))
        if no != nc:
            errs.append(f"unbalanced {open_kw}/{close_kw}: {no} vs {nc}")
    ok = not errs
    return CompileResult(
        ok=ok,
        tool="basic-syntax (NOT a compiler)",
        stderr="; ".join(errs),
        stdout="ok" if ok else "",
    )
