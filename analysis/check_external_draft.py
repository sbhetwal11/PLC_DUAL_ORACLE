"""End-to-end verification of the EXTERNAL family-level test-set DRAFT.

Loads every task under external_testset_draft/tasks/ with the real plcbench
loader (pointed at the draft dir via load_all(<dir>)), runs the full dual-oracle
harness on each reference (MATIEC compile + nuXmv verify + interpreter scenarios),
and additionally audits two subset rules the draft must satisfy:
  - no reference reads a TON's Q before that timer's call in scan order
  - no reference uses the T#1s preset (whole-second presets must be >= 2 s)

Run: wsl bash toolchain/wsl_analysis.sh analysis/check_external_draft.py
"""
from __future__ import annotations
import os, re, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness
from plcbench.st.parser import (Assign, Binary, Case, If, TimerCall, Unary, Var,
                                parse_program)

DRAFT_DIR = Path(__file__).resolve().parent.parent / "external_testset_draft" / "tasks"


def reads_q_before_call(src: str) -> bool:
    """True if any TON's .Q is read before that timer's call in scan order."""
    prog = parse_program(src)
    timers = {d.name for d in prog.decls if d.type == "TON"}
    if not timers:
        return False
    called: set = set()
    hit = [False]

    def expr(e):
        if isinstance(e, Var):
            if "." in e.name:
                base, mem = e.name.split(".", 1)
                if base in timers and mem.upper() == "Q" and base not in called:
                    hit[0] = True
        elif isinstance(e, Unary):
            expr(e.operand)
        elif isinstance(e, Binary):
            expr(e.left); expr(e.right)

    def walk(stmts):
        for s in stmts:
            if isinstance(s, Assign):
                expr(s.expr)
            elif isinstance(s, TimerCall):
                expr(s.in_expr); expr(s.pt); called.add(s.instance)
            elif isinstance(s, If):
                for c, b in s.branches:
                    expr(c); walk(b)
                walk(s.orelse)
            elif isinstance(s, Case):
                expr(s.selector)
                for _, b in s.branches:
                    walk(b)
                walk(s.orelse)

    walk(prog.body)
    return hit[0]


def uses_t1s(src: str) -> bool:
    # any TIME literal of exactly 1 second (T#1s), case-insensitive, not T#10s/T#1m
    return bool(re.search(r"T#0*1\s*s(?![0-9a-zA-Z])", src, re.IGNORECASE))


def main():
    lts = sorted(load_all(DRAFT_DIR), key=lambda lt: lt.id)
    print(f"# External draft verification  ({len(lts)} tasks from {DRAFT_DIR})\n")
    n_ok = 0
    problems = []
    for lt in lts:
        ev = harness.evaluate(lt.task, lt.reference_st)
        compile_ok = ev.compiles is True
        verify_ok = ev.verified is True and ev.n_props_pass == ev.n_props and ev.n_props > 0
        scen_ok = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
        qbad = reads_q_before_call(lt.reference_st)
        t1s = uses_t1s(lt.reference_st)
        all_ok = compile_ok and verify_ok and scen_ok and not qbad and not t1s
        n_ok += all_ok
        flag = "OK " if all_ok else "XX "
        print(f"{flag}{lt.id:42s} compile={ {True:'OK',False:'FAIL',None:'n/a'}[ev.compiles] :4s} "
              f"verify={ {True:'OK',False:'FAIL',None:'n/a'}[ev.verified] :4s} "
              f"props={ev.n_props_pass}/{ev.n_props} "
              f"scen={ev.scenarios_pass}/{ev.scenarios_total} "
              f"Qbeforecall={qbad} T#1s={t1s}")
        if not all_ok:
            detail = []
            if not compile_ok:
                detail.append("COMPILE: " + (ev.compile_stderr or "")[-300:])
            if not verify_ok and ev.verify is not None:
                for p in ev.verify.properties:
                    if p.status != "pass":
                        detail.append(f"PROP {p.property_id}={p.status} {(p.detail or '')[:200]}")
            if not scen_ok:
                sres = None
                from plcbench.backends import simulate
                sres = simulate.run_scenarios(lt.task, lt.reference_st)
                detail.append("SCEN: " + sres.detail + " " + str(sres.per_scenario))
            if qbad:
                detail.append("reads timer Q before its call")
            if t1s:
                detail.append("uses T#1s")
            problems.append((lt.id, detail))

    print(f"\nSUMMARY: {n_ok}/{len(lts)} references pass all gates "
          f"(compile + verify + scenarios + no-Q-before-call + no-T#1s)")
    for tid, det in problems:
        print(f"\n--- {tid} ---")
        for d in det:
            print("   " + d)
    return 0 if n_ok == len(lts) else 1


if __name__ == "__main__":
    sys.exit(main())
