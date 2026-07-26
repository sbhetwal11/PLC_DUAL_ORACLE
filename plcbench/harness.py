"""Harness: run the available backends over a candidate ST solution and score it.

Scoring (verified correctness, the headline metric):
  - compiles:  the ST compiles (MATIEC)
  - verified:  compiles AND every safety property passes the model-checker
On a bare laptop (no tools) results are reported as 'unavailable' rather than
faked, so numbers are never misleading.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .backends import VerifyResult
from .backends import compile_matiec, simulate, verify_nuxmv
from .loader import LoadedTask
from .schema import Task


@dataclass
class TaskEvaluation:
    task_id: str
    compiles: bool | None        # None = compiler unavailable
    verified: bool | None        # None = verifier unavailable
    compile_tool: str = ""
    verify_tool: str = ""
    n_props: int = 0
    n_props_pass: int = 0
    scenarios_total: int = 0
    scenarios_pass: int = 0
    scenarios_parse_ok: bool = True
    compile_stderr: str = ""
    verify: VerifyResult | None = field(default=None, repr=False)

    def summary(self) -> str:
        c = {True: "OK", False: "FAIL", None: "n/a"}[self.compiles]
        v = {True: "OK", False: "FAIL", None: "n/a"}[self.verified]
        return (f"{self.task_id:32s} compile={c:4s} verify={v:4s} "
                f"props={self.n_props_pass}/{self.n_props} "
                f"scenarios={self.scenarios_pass}/{self.scenarios_total}")


def evaluate(task: Task, st_code: str) -> TaskEvaluation:
    cres = compile_matiec.compile_st(st_code)
    compiles = cres.ok if cres.available else None

    sres = simulate.run_scenarios(task, st_code)

    vres = verify_nuxmv.verify(task, st_code)
    if not vres.available:
        verified = None
        n_pass = 0
    else:
        n_pass = sum(1 for p in vres.properties if p.status == "pass")
        verified = (compiles is not False) and (n_pass == len(task.safety_properties))

    return TaskEvaluation(
        task_id=task.id,
        compiles=compiles,
        verified=verified,
        compile_tool=cres.tool,
        verify_tool=vres.tool,
        n_props=len(task.safety_properties),
        n_props_pass=n_pass,
        scenarios_total=sres.total,
        scenarios_pass=sres.passed,
        scenarios_parse_ok=sres.parse_ok,
        compile_stderr=cres.stderr,
        verify=vres,
    )


def evaluate_loaded(lt: LoadedTask) -> TaskEvaluation:
    """Sanity path: evaluate a task's own reference solution."""
    return evaluate(lt.task, lt.reference_st)
