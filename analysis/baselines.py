"""Degenerate-baseline evaluation (DeepReview B1/B4/M30).

For each task, build degenerate controllers by reusing the reference solution's
declaration block and replacing only the body, then score each on all four
dimensions with the real harness (MATIEC compile + nuXmv invariants + scenario
interpreter):

  - all-off      : every output driven to its OFF value (BOOL FALSE, INT range-low)
  - all-on       : every output driven to its ON value  (BOOL TRUE,  INT range-high)
  - empty-body   : declarations only, no statements (outputs keep init state)

Reports, per baseline and per tier: compile rate, invariant-pass rate
(compile AND all properties hold), scenario-all-pass rate, and task-valid rate
(compile AND invariants AND all scenarios pass).

Run inside WSL with NUXMV_BIN and MATIEC_IEC2C exported (see toolchain/wsl_eval.sh).
"""
from __future__ import annotations
import json, re, sys, os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness


def header_of(ref_st: str) -> tuple[str, str]:
    """Return (program_name, declaration_header_through_last_END_VAR)."""
    m = re.search(r"\bPROGRAM\s+(\w+)", ref_st)
    name = m.group(1) if m else "prog"
    # find last END_VAR
    ends = [mm.end() for mm in re.finditer(r"\bEND_VAR\b", ref_st)]
    if not ends:
        # no VAR blocks; header is just the PROGRAM line
        line_end = ref_st.index("\n", m.start()) if m else 0
        return name, ref_st[:line_end + 1]
    return name, ref_st[:ends[-1]] + "\n"


def outputs_of(task):
    return [v for v in task.interface if v.direction.value == "output"]


def off_val(v):
    if v.type == "BOOL":
        return "FALSE"
    lo = int(v.range[0]) if v.range else 0
    return str(lo)


def on_val(v):
    if v.type == "BOOL":
        return "TRUE"
    hi = int(v.range[1]) if v.range else 1
    return str(hi)


def build(task, ref_st, mode):
    name, header = header_of(ref_st)
    outs = outputs_of(task)
    body_lines = []
    if mode == "all-off":
        body_lines = [f"    {v.name} := {off_val(v)};" for v in outs]
    elif mode == "all-on":
        body_lines = [f"    {v.name} := {on_val(v)};" for v in outs]
    elif mode == "empty-body":
        body_lines = []
    body = "\n".join(body_lines)
    return f"{header}\n{body}\n\nEND_PROGRAM\n"


def dims(ev):
    compile_ok = ev.compiles is True
    inv_ok = ev.verified is True                       # compile AND all props
    scen_ok = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
    taskvalid = compile_ok and inv_ok and scen_ok
    return compile_ok, inv_ok, scen_ok, taskvalid


def main():
    tasks = load_all()
    modes = ["all-off", "all-on", "empty-body"]
    # per mode: list of (tier, taskid, compile, inv, scen, taskvalid, npass, ntot, spass, stot)
    rows = defaultdict(list)
    for lt in tasks:
        t = lt.task
        for mode in modes:
            st = build(t, lt.reference_st, mode)
            ev = harness.evaluate(t, st)
            c, i, s, tv = dims(ev)
            rows[mode].append((t.difficulty.value, t.id, c, i, s, tv,
                               ev.n_props_pass, ev.n_props,
                               ev.scenarios_pass, ev.scenarios_total))

    order = {"easy": 0, "medium": 1, "hard": 2}
    n = len(tasks)
    print(f"# Degenerate-baseline sweep over {n} tasks (real harness: MATIEC + nuXmv + scenarios)\n")
    summary = {}
    for mode in modes:
        rs = sorted(rows[mode], key=lambda r: (order[r[0]], r[1]))
        comp = sum(r[2] for r in rs)
        inv = sum(r[3] for r in rs)
        scen = sum(r[4] for r in rs)
        tv = sum(r[5] for r in rs)
        by_tier = defaultdict(lambda: [0, 0, 0, 0, 0])
        for r in rs:
            bt = by_tier[r[0]]
            bt[0] += 1; bt[1] += r[2]; bt[2] += r[3]; bt[3] += r[4]; bt[4] += r[5]
        print(f"## {mode}")
        print(f"   compile   {comp}/{n} = {comp/n:.3f}")
        print(f"   invariant {inv}/{n} = {inv/n:.3f}   (compile AND all properties)")
        print(f"   scenario  {scen}/{n} = {scen/n:.3f}   (all scenarios pass)")
        print(f"   TASK-VALID {tv}/{n} = {tv/n:.3f}   (compile AND invariant AND scenario)")
        for tier in ["easy", "medium", "hard"]:
            b = by_tier[tier]
            if b[0]:
                print(f"     {tier:6s}: compile {b[1]}/{b[0]}  inv {b[2]}/{b[0]}  scen {b[3]}/{b[0]}  taskvalid {b[4]}/{b[0]}")
        # list which tasks the baseline "passes" on invariant but fails scenario
        leak = [r[1] for r in rs if r[3] and not r[4]]
        print(f"   invariant-pass-but-scenario-fail ({len(leak)}): {', '.join(leak)}")
        print()
        summary[mode] = {
            "compile": comp, "invariant": inv, "scenario": scen, "taskvalid": tv, "n": n,
            "by_tier": {k: v for k, v in by_tier.items()},
            "rows": rs,
        }
    with open("results/baselines.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, default=str)
    print("wrote results/baselines.json")


if __name__ == "__main__":
    main()
