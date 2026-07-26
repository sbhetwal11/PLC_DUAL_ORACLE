"""ITEM 8: ground-truth category -> reward table for the three reward functions in
finetune/reward.py, computed by DRIVING THE ACTUAL reward code (not re-deriving it).

We monkeypatch finetune.reward.{extract_st, parse_program, evaluate} so we can feed a
controlled plcbench.harness.TaskEvaluation for each harness outcome category, then call
dual_oracle_reward (Eq 2), task_valid_reward (Eq 3), reward_taskvalid_gated (Sec S.XVIII)
and record exactly what each returns. No nuXmv / MATIEC needed.

Run: wsl bash toolchain/wsl_analysis.sh analysis/reward_category_table.py
Writes results/reward_category_table.json
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import finetune.reward as R
from plcbench.harness import TaskEvaluation
from plcbench.backends import PropertyResult, VerifyResult
from plcbench.schema import Task

# meta with P1 critical, P2 high (mirrors analysis/test_gated_reward.py)
META = {
    "id": "T_TEST", "title": "t", "difficulty": "easy", "domain": "test",
    "nl_spec": "toy",
    "interface": [{"name": "A", "type": "BOOL", "direction": "input"},
                  {"name": "B", "type": "BOOL", "direction": "output"}],
    "safety_properties": [
        {"id": "P1", "kind": "safety", "severity": "critical", "nl": "c", "ltl": "G(A)"},
        {"id": "P2", "kind": "safety", "severity": "high", "nl": "h", "ltl": "G(A)"}],
}


def make_ev(compiles, prop_status, verify_available, n_pass,
            scen_total=2, scen_pass=2):
    """Build a TaskEvaluation. prop_status = list[(pid,status)]."""
    vr = VerifyResult(tool="nuXmv", available=verify_available,
                      properties=[PropertyResult(property_id=pid, status=st)
                                  for pid, st in prop_status])
    return TaskEvaluation(
        task_id="T_TEST", compiles=compiles, verified=None,
        n_props=len(prop_status), n_props_pass=n_pass,
        scenarios_total=scen_total, scenarios_pass=scen_pass, verify=vr)


# Each case: (label, how-to-raise/evaluate). We patch evaluate per-case.
def run_case(ev_or_exc, parse_raises=False):
    R.extract_st = lambda c: c
    if parse_raises:
        def _p(_c):
            raise R.STSyntaxError("unparseable")
        R.parse_program = _p
    else:
        R.parse_program = lambda _c: None
    if isinstance(ev_or_exc, Exception):
        def _e(_t, _c):
            raise ev_or_exc
        R.evaluate = _e
    else:
        R.evaluate = lambda _t, _c: ev_or_exc
    d = R.dual_oracle_reward(META, "X")
    tv = R.task_valid_reward(META, "X")
    g = R.reward_taskvalid_gated(META, "X")
    return d, tv, g


CASES = [
    # (category, description, ev builder or exception, parse_raises)
    ("parse_error", "completion does not parse (translator front-end reject)",
     None, True),
    ("compile_error", "parses; MATIEC rejects (compiles=False)",
     make_ev(False, [("P1", "unknown"), ("P2", "unknown")], True, 0), False),
    ("translate_error", "parses+compiles(True); ST->SMV lowering fails -> all props status=error, n_pass=0",
     make_ev(True, [("P1", "error"), ("P2", "error")], True, 0), False),
    ("verified", "compiles(True); all props pass; scen 2/2",
     make_ev(True, [("P1", "pass"), ("P2", "pass")], True, 2, 2, 2), False),
    ("unsafe_noncrit_fails", "compiles(True); critical P1 pass, non-crit P2 FAIL (n_pass=1); scen 2/2",
     make_ev(True, [("P1", "pass"), ("P2", "fail")], True, 1, 2, 2), False),
    ("unsafe_crit_fails", "compiles(True); critical P1 FAIL, P2 pass (n_pass=1); scen 2/2",
     make_ev(True, [("P1", "fail"), ("P2", "pass")], True, 1, 2, 2), False),
    ("verify_unavailable", "compiles(True); nuXmv unavailable -> props status=unavailable, n_pass=0; scen 2/2",
     make_ev(True, [("P1", "unavailable"), ("P2", "unavailable")], False, 0, 2, 2), False),
    ("timeout_partial", "compiles(True); P1 pass, P2 nuXmv TIMEOUT(status=unknown) n_pass=1; scen 2/2",
     make_ev(True, [("P1", "pass"), ("P2", "unknown")], True, 1, 2, 2), False),
    ("timeout_all", "compiles(True); BOTH props timeout(status=unknown) n_pass=0; scen 2/2",
     make_ev(True, [("P1", "unknown"), ("P2", "unknown")], True, 0, 2, 2), False),
    ("oracle_exception", "evaluate()/subprocess raises (arbitrary-bytes guard) -> outer except",
     RuntimeError("oracle/subprocess hiccup"), False),
    # scenarioless variants (task carries no functional oracle)
    ("verified_scenarioless", "compiles(True); all props pass; scenarios_total=0",
     make_ev(True, [("P1", "pass"), ("P2", "pass")], True, 2, 0, 0), False),
    ("translate_error_scenarioless", "compiles(True); props error; scenarios_total=0",
     make_ev(True, [("P1", "error"), ("P2", "error")], True, 0, 0, 0), False),
]

rows = []
for cat, desc, ev, praise in CASES:
    d, tv, g = run_case(ev, parse_raises=praise)
    rows.append({"category": cat, "description": desc,
                 "dual_oracle_reward_Eq2": d,
                 "task_valid_reward_Eq3": tv,
                 "reward_taskvalid_gated": g})

os.makedirs("results", exist_ok=True)
json.dump({"meta": "P1=critical,P2=high; n_props=2; scen 2/2 unless noted", "rows": rows},
          open("results/reward_category_table.json", "w"), indent=1)

w = max(len(r["category"]) for r in rows)
print(f"{'category':{w}s}  {'Eq2 dual':>9s} {'Eq3 taskvalid':>14s} {'gated':>7s}")
for r in rows:
    print(f"{r['category']:{w}s}  {r['dual_oracle_reward_Eq2']:>9} "
          f"{r['task_valid_reward_Eq3']:>14} {r['reward_taskvalid_gated']:>7}")
print("\nwrote results/reward_category_table.json")
