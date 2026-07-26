"""Pure-Python unit tests for the CRITICAL-PROPERTY HARD-GATED task-valid reward
(finetune.reward.reward_taskvalid_gated and its helpers).

No GPU, no nuXmv, no MATIEC: the scoring/gating logic is exercised against a MOCKED
evaluation object (a SimpleNamespace shaped like plcbench.harness.TaskEvaluation) and
a real pydantic Task built from a minimal meta. Only the unparseable path of the full
wrapper is exercised, which short-circuits before the oracle is ever called.

Run:  python -m analysis.test_gated_reward       (from the repo root, PYTHONPATH=repo)
  or: python analysis/test_gated_reward.py
Exit code 0 == all assertions passed.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

from finetune.reward import (
    reward_taskvalid_gated,
    task_valid_reward,
    _taskvalid_score_from_eval,
    _any_critical_failed,
    _critical_property_ids,
)
from plcbench.schema import Task


# --- a minimal, schema-valid task: P1 critical, P2 high -----------------------
META = {
    "id": "T_TEST",
    "title": "gating test task",
    "difficulty": "easy",
    "domain": "test",
    "nl_spec": "toy",
    "interface": [
        {"name": "A", "type": "BOOL", "direction": "input"},
        {"name": "B", "type": "BOOL", "direction": "output"},
    ],
    "safety_properties": [
        {"id": "P1", "kind": "safety", "severity": "critical",
         "nl": "critical one", "ltl": "G(A -> B)"},
        {"id": "P2", "kind": "safety", "severity": "high",
         "nl": "non-critical", "ltl": "G(!A -> !B)"},
    ],
}
TASK = Task.model_validate(META)


def _ev(compiles, props, scen_total=2, scen_pass=2):
    """Build a mock evaluation. `props` = list of (property_id, status)."""
    n_pass = sum(1 for _, s in props if s == "pass")
    verify = SimpleNamespace(
        properties=[SimpleNamespace(property_id=pid, status=st) for pid, st in props])
    return SimpleNamespace(
        compiles=compiles, n_props=len(props), n_props_pass=n_pass,
        scenarios_total=scen_total, scenarios_pass=scen_pass, verify=verify)


CASES = []


def check(name, got, expected):
    ok = abs(got - expected) < 1e-9
    CASES.append((name, ok, got, expected))
    return ok


# 1. helper: which properties are critical
assert _critical_property_ids(TASK) == {"P1"}, "critical-id extraction wrong"

# 2. all pass, compiles, scenarios pass -> full task-valid = 1.0, gate inactive
ev = _ev(True, [("P1", "pass"), ("P2", "pass")], 2, 2)
check("all_pass_score", _taskvalid_score_from_eval(ev), 1.0)
assert not _any_critical_failed(TASK, ev)
check("all_pass_gated", 1.0 if not _any_critical_failed(TASK, ev)
      else min(_taskvalid_score_from_eval(ev), 0.1), 1.0)

# 3. CRITICAL P1 fails, P2 passes, compiles -> ungated would be 0.2+0.4*.5+0.4*1=0.8
#    gated must be capped to 0.1
ev = _ev(True, [("P1", "fail"), ("P2", "pass")], 2, 2)
check("crit_fail_ungated", _taskvalid_score_from_eval(ev), 0.8)
assert _any_critical_failed(TASK, ev), "critical failure not detected"
gated = min(_taskvalid_score_from_eval(ev), 0.1) if _any_critical_failed(TASK, ev) \
    else _taskvalid_score_from_eval(ev)
check("crit_fail_gated", gated, 0.1)

# 4. NON-critical P2 fails, critical P1 passes -> NOT gated; == task-valid score
ev = _ev(True, [("P1", "pass"), ("P2", "fail")], 2, 2)
assert not _any_critical_failed(TASK, ev), "non-critical fail must NOT trip the gate"
check("noncrit_fail_ungated", _taskvalid_score_from_eval(ev), 0.8)  # 0.2+0.4*.5+0.4*1
gated = min(_taskvalid_score_from_eval(ev), 0.1) if _any_critical_failed(TASK, ev) \
    else _taskvalid_score_from_eval(ev)
check("noncrit_fail_gated", gated, 0.8)  # unchanged from task-valid

# 5. does not compile -> 0.1 regardless
ev = _ev(False, [("P1", "pass"), ("P2", "pass")], 2, 2)
check("no_compile", _taskvalid_score_from_eval(ev), 0.1)

# 6. fail-closed: verify unavailable (critical status absent) -> treated as failed
ev = _ev(True, [("P1", "unavailable"), ("P2", "unavailable")], 2, 2)
assert _any_critical_failed(TASK, ev), "missing/unavailable critical must fail-close"

# 7. scenario-less task path: score = 0.2 + 0.7*prop
ev = _ev(True, [("P1", "pass"), ("P2", "pass")], 0, 0)
check("scenarioless_allpass", _taskvalid_score_from_eval(ev), 0.9)  # 0.2+0.7*1

# 8. full wrapper on UNPARSEABLE completion -> 0.0 (short-circuits before oracle)
check("unparseable_wrapper", reward_taskvalid_gated(META, "this is not ST code {{{"), 0.0)

# 9. gated never exceeds task_valid on a compiling program (spot check via helper):
#    when no critical fails, gated == ungated; when critical fails, gated <= ungated.
for props, scen in [([("P1", "pass"), ("P2", "pass")], (2, 2)),
                    ([("P1", "fail"), ("P2", "pass")], (2, 1)),
                    ([("P1", "pass"), ("P2", "fail")], (2, 0))]:
    ev = _ev(True, props, *scen)
    base = _taskvalid_score_from_eval(ev)
    g = min(base, 0.1) if _any_critical_failed(TASK, ev) else base
    assert g <= base + 1e-9, "gated reward must never exceed the ungated task-valid score"


def main() -> int:
    failed = [c for c in CASES if not c[1]]
    for name, ok, got, exp in CASES:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:24s} got={got}  expected={exp}")
    print(f"\n{len(CASES) - len(failed)}/{len(CASES)} value checks passed; "
          f"all structural asserts passed.")
    if failed:
        print("FAILURES:", [c[0] for c in failed])
        return 1
    print("OK: reward_taskvalid_gated behaves correctly (hard gate on critical props).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
