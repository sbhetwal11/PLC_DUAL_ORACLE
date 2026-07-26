"""Scenario-simulation backend (pure Python, always available).

Executes a candidate ST solution against a task's scenarios using the ST
interpreter. Complements model-checking: cheap, needs no external tools, and
catches functional regressions immediately.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..schema import Task
from ..st import STSyntaxError
from ..st.interp import check_scenarios_src


@dataclass
class ScenarioResult:
    total: int
    passed: int
    parse_ok: bool
    detail: str = ""
    per_scenario: list = field(default_factory=list)  # (id, ok, detail)


def run_scenarios(task: Task, st_code: str) -> ScenarioResult:
    if not task.scenarios:
        return ScenarioResult(total=0, passed=0, parse_ok=True, detail="no scenarios")
    try:
        results = check_scenarios_src(st_code, task.scenarios)
    except STSyntaxError as e:
        return ScenarioResult(total=len(task.scenarios), passed=0, parse_ok=False,
                              detail=f"parse error: {e}")
    except Exception as e:  # noqa: BLE001  (interpreter runtime issue)
        return ScenarioResult(total=len(task.scenarios), passed=0, parse_ok=True,
                              detail=f"runtime error: {e}")
    passed = sum(1 for _, ok, _ in results if ok)
    return ScenarioResult(total=len(results), passed=passed, parse_ok=True,
                          per_scenario=results)
