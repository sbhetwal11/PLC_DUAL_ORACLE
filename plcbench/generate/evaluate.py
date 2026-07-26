"""Run a generator over the benchmark and aggregate metrics.

Each candidate is placed in exactly one OUTCOME CATEGORY so failures are
interpretable (a syntax slip is very different from genuinely unsafe logic):
  - parse_error      : not valid ST in the supported subset (won't parse)
  - translate_error  : parses but can't be lowered to the model checker
  - unsafe           : verifies fine but at least one SAFETY PROPERTY FAILS
  - verified         : compiles + every safety property holds (the goal)
  - verify_unavailable : nuXmv not present (run in WSL/Docker to get real numbers)
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from ..harness import evaluate
from ..loader import load_all
from ..st import STSyntaxError, parse_program


@dataclass
class EvalRow:
    task_id: str
    difficulty: str
    category: str
    verified: bool | None
    n_props: int
    n_props_pass: int
    scenarios_total: int
    scenarios_pass: int
    detail: str = ""
    code: str = ""
    error: str = ""


def _categorize(parsed: bool, ev) -> str:
    if not parsed:
        return "parse_error"
    if ev.compiles is False:          # MATIEC rejected it (real-compiler invalid)
        return "compile_error"
    vr = ev.verify
    if not vr or not vr.available:
        return "verify_unavailable"
    statuses = [p.status for p in vr.properties]
    if any(s == "error" for s in statuses):
        return "translate_error"
    if statuses and all(s == "pass" for s in statuses):
        return "verified"
    if any(s == "fail" for s in statuses):
        return "unsafe"
    return "unknown"


@dataclass
class EvalReport:
    model: str
    rows: list = field(default_factory=list)

    def summary(self) -> dict:
        n = len(self.rows)
        ok = [r for r in self.rows if not r.error]
        cats = Counter(r.category for r in ok)
        props_total = sum(r.n_props for r in ok)
        props_pass = sum(r.n_props_pass for r in ok)
        scen_total = sum(r.scenarios_total for r in ok)
        scen_pass = sum(r.scenarios_pass for r in ok)
        return {
            "model": self.model,
            "tasks": n,
            "api_errors": n - len(ok),
            "verified_rate": round(cats["verified"] / n, 3) if n else 0.0,
            "unsafe_rate": round(cats["unsafe"] / n, 3) if n else 0.0,
            "parse_error_rate": round(cats["parse_error"] / n, 3) if n else 0.0,
            "compile_error_rate": round(cats["compile_error"] / n, 3) if n else 0.0,
            "translate_error_rate": round(cats["translate_error"] / n, 3) if n else 0.0,
            "property_pass_rate": round(props_pass / props_total, 3) if props_total else 0.0,
            "scenario_pass_rate": round(scen_pass / scen_total, 3) if scen_total else 0.0,
            "categories": dict(cats),
        }

    def by_tier(self) -> dict:
        out = {}
        for tier in ("easy", "medium", "hard"):
            rs = [r for r in self.rows if r.difficulty == tier and not r.error]
            if rs:
                out[tier] = round(sum(1 for r in rs if r.category == "verified") / len(rs), 3)
        return out


def run_eval(generator, tasks=None) -> EvalReport:
    tasks = tasks or load_all()
    rep = EvalReport(model=getattr(generator, "name", "?"))
    for lt in tasks:
        try:
            code = generator.generate(lt)
        except Exception as e:  # noqa: BLE001 (API/network failure)
            rep.rows.append(EvalRow(
                task_id=lt.id, difficulty=lt.task.difficulty.value, category="api_error",
                verified=None, n_props=0, n_props_pass=0, scenarios_total=0,
                scenarios_pass=0, error=str(e)[:200]))
            continue
        ev = evaluate(lt.task, code)
        try:
            parse_program(code)
            parsed = True
        except (STSyntaxError, Exception):
            parsed = False
        rep.rows.append(EvalRow(
            task_id=lt.id, difficulty=lt.task.difficulty.value,
            category=_categorize(parsed, ev), verified=ev.verified,
            n_props=ev.n_props, n_props_pass=ev.n_props_pass,
            scenarios_total=ev.scenarios_total, scenarios_pass=ev.scenarios_pass,
            detail=ev.compile_stderr[:120], code=code))
    return rep


# ----------------------------------------------------------------- pass@k
def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k (Chen et al., Codex): prob >=1 of k samples is correct,
    given c of n samples are correct."""
    if k > n:
        k = n
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


@dataclass
class PassKRow:
    task_id: str
    difficulty: str
    n: int            # samples actually generated (API failures excluded)
    c_verified: int   # samples that were verified-safe


@dataclass
class PassKReport:
    model: str
    n_samples: int
    temperature: float
    ks: list
    rows: list = field(default_factory=list)

    def summary(self) -> dict:
        out = {"model": self.model, "n_samples": self.n_samples,
               "temperature": self.temperature, "tasks": len(self.rows)}
        for k in self.ks:
            vals = [pass_at_k(r.n, r.c_verified, k) for r in self.rows if r.n > 0]
            out[f"pass@{k}"] = round(sum(vals) / len(vals), 3) if vals else 0.0
        return out

    def by_tier(self) -> dict:
        out = {}
        for tier in ("easy", "medium", "hard"):
            rs = [r for r in self.rows if r.difficulty == tier and r.n > 0]
            if rs:
                out[tier] = {f"pass@{k}": round(
                    sum(pass_at_k(r.n, r.c_verified, k) for r in rs) / len(rs), 3)
                    for k in self.ks}
        return out


def _seed_everything(seed: int) -> None:
    import random
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:  # noqa: BLE001
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:  # noqa: BLE001
        pass


def run_eval_passk(generator, n_samples: int, ks: list, temperature: float = 0.8,
                   tasks=None, seed: int | None = None) -> PassKReport:
    if seed is not None:
        _seed_everything(seed)
    tasks = tasks or load_all()
    rep = PassKReport(model=getattr(generator, "name", "?"), n_samples=n_samples,
                      temperature=temperature, ks=ks)
    for lt in tasks:
        n = c = 0
        for _ in range(n_samples):
            try:
                code = generator.generate(lt, temperature=temperature)
            except Exception:  # noqa: BLE001 (API failure: skip this sample)
                continue
            n += 1
            ev = evaluate(lt.task, code)
            try:
                parse_program(code)
                parsed = True
            except (STSyntaxError, Exception):
                parsed = False
            if _categorize(parsed, ev) == "verified":
                c += 1
        rep.rows.append(PassKRow(task_id=lt.id, difficulty=lt.task.difficulty.value,
                                 n=n, c_verified=c))
    return rep
