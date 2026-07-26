"""Verification backends + their shared result types.

Each backend is optional and self-reports availability via .available(), so the
harness runs end-to-end on a laptop with no external tools (reporting
'unavailable' results) and gains real compile/model-check results once the
Phase-B toolchain (Docker: MATIEC + nuXmv) is built.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CompileResult:
    ok: bool
    tool: str
    stdout: str = ""
    stderr: str = ""
    available: bool = True   # was the backing tool present?


@dataclass
class PropertyResult:
    property_id: str
    status: str              # "pass" | "fail" | "unknown" | "error" | "unavailable"
    tool: str = ""
    counterexample: str = "" # model-checker CEX (drives Phase-C repair/reward)
    detail: str = ""


@dataclass
class VerifyResult:
    tool: str
    available: bool
    properties: list[PropertyResult] = field(default_factory=list)
