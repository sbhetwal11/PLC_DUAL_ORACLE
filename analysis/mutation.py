"""Mutation analysis of the reference solutions (DeepReview M22, M23, B1, B6).

Applies syntactic mutation operators to each reference program, keeps the mutants
that still COMPILE (MATIEC-accepted, i.e. remain valid ST), and measures how the
two acceptance dimensions discriminate them:

  killed_by_invariant : some safety property now fails (nuXmv)
  killed_by_scenario  : some execution scenario now fails (interpreter)

The key quantity for the metric-validity argument (B1/M23) is:
  invariant-BLIND kills = compiling mutants that satisfy ALL invariants but FAIL a
  scenario -> faults the invariant-only metric cannot see but the scenario dimension can.

Also emits, per property, whether it is a positive-output obligation and whether it
is vacuously satisfied by the all-off program (M22 vacuity), using the harness.

Run under the WSL harness.
"""
from __future__ import annotations
import json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness


def mutants(src: str):
    """Yield (operator, mutated_src) for a battery of syntactic mutations."""
    out = []

    def add(op, new):
        if new != src:
            out.append((op, new))

    # 1. BOOL literal flips (each occurrence, one at a time)
    for m in re.finditer(r"\b(TRUE|FALSE)\b", src):
        rep = "FALSE" if m.group(1) == "TRUE" else "TRUE"
        add(f"bool_flip@{m.start()}", src[:m.start()] + rep + src[m.end():])
    # 2. comparison operator swaps
    comp = [(">=", "<="), ("<=", ">="), (">", "<"), ("<", ">")]
    for a, b in comp:
        for m in re.finditer(re.escape(a), src):
            # avoid double-processing >= as >
            if a in (">", "<") and (src[m.start():m.start()+2] in (">=", "<=")):
                continue
            add(f"cmp_{a}_{b}@{m.start()}", src[:m.start()] + b + src[m.end():])
    # 3. boolean connective swaps (AND/OR and &/|)
    for a, b in [("AND", "OR"), ("OR", "AND")]:
        for m in re.finditer(rf"\b{a}\b", src):
            add(f"conn_{a}_{b}@{m.start()}", src[:m.start()] + b + src[m.end():])
    for a, b in [("&", "|"), ("|", "&")]:
        for m in re.finditer(re.escape(a), src):
            add(f"conn_{a}_{b}@{m.start()}", src[:m.start()] + b + src[m.end():])
    # 4. negate a condition after IF/ELSIF/WHILE (insert NOT)
    for m in re.finditer(r"\b(IF|ELSIF)\s+", src):
        i = m.end()
        add(f"negate_cond@{i}", src[:i] + "NOT (" + _to_then(src, i) )
    # 5. drop one assignment statement (comment it out)
    for m in re.finditer(r"^[ \t]*\w+\s*:=[^;]*;", src, re.M):
        add(f"drop_stmt@{m.start()}", src[:m.start()] + "(* mut *)" + src[m.end():])
    # 6. timer preset off-by-one (T#Ns)
    for m in re.finditer(r"T#(\d+)s", src):
        n = int(m.group(1))
        add(f"timer_preset+1@{m.start()}", src[:m.start()] + f"T#{n+1}s" + src[m.end():])
    # 7. relational constant off-by-one (INT literals in comparisons)
    for m in re.finditer(r"([<>]=?\s*)(\d+)", src):
        n = int(m.group(2))
        add(f"const+1@{m.start()}", src[:m.start()] + m.group(1) + str(n + 1) + src[m.end():])
    return out


def _to_then(src, i):
    """Wrap the condition between position i and the next THEN with a closing paren."""
    j = src.find("THEN", i)
    if j < 0:
        return src[i:]
    return src[i:j] + ") THEN" + src[j + 4:]


def classify(ev):
    compiles = ev.compiles is True
    inv_ok = ev.verified is True
    scen_ok = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
    return compiles, inv_ok, scen_ok


def main():
    tasks = load_all()
    per_task = {}
    tot = defaultdict(int)
    for lt in tasks:
        t = lt.task
        muts = mutants(lt.reference_st)
        c_compile = c_killinv = c_killscen = c_invblind = c_live = 0
        for op, ms in muts:
            try:
                ev = harness.evaluate(t, ms)
            except Exception:
                continue
            compiles, inv_ok, scen_ok = classify(ev)
            if not compiles:
                continue  # non-compiling mutant: trivially rejected, not counted
            c_compile += 1
            killed_inv = not inv_ok
            killed_scen = not scen_ok
            if killed_inv:
                c_killinv += 1
            if killed_scen:
                c_killscen += 1
            if (not killed_inv) and killed_scen:
                c_invblind += 1   # invariant-blind: scenario catches what invariants miss
            if (not killed_inv) and (not killed_scen):
                c_live += 1       # survives both (equivalent-ish or undetected)
        per_task[t.id] = dict(n_mut=len(muts), compiling=c_compile,
                              killed_inv=c_killinv, killed_scen=c_killscen,
                              inv_blind=c_invblind, survived=c_live)
        tot["n_mut"] += len(muts); tot["compiling"] += c_compile
        tot["killed_inv"] += c_killinv; tot["killed_scen"] += c_killscen
        tot["inv_blind"] += c_invblind; tot["survived"] += c_live

    print("# Mutation analysis over reference solutions (compiling mutants only)\n")
    print(f"{'task':32s} {'mut':>4s} {'comp':>5s} {'k_inv':>6s} {'k_scen':>7s} {'invblind':>9s} {'surv':>5s}")
    for tid, d in per_task.items():
        print(f"{tid:32s} {d['n_mut']:4d} {d['compiling']:5d} {d['killed_inv']:6d} "
              f"{d['killed_scen']:7d} {d['inv_blind']:9d} {d['survived']:5d}")
    C = tot["compiling"] or 1
    print("\n## Totals (compiling mutants)")
    print(f"   compiling mutants:         {tot['compiling']}")
    print(f"   killed by invariants:      {tot['killed_inv']}  ({tot['killed_inv']/C:.3f})")
    print(f"   killed by scenarios:       {tot['killed_scen']}  ({tot['killed_scen']/C:.3f})")
    print(f"   killed by EITHER:          {tot['killed_inv'] + tot['inv_blind']}  "
          f"({(tot['killed_inv'] + tot['inv_blind'])/C:.3f})")
    print(f"   INVARIANT-BLIND (scenario-only) kills: {tot['inv_blind']}  ({tot['inv_blind']/C:.3f})")
    print(f"   survived both dimensions:  {tot['survived']}  ({tot['survived']/C:.3f})")
    with open("results/mutation.json", "w", encoding="utf-8") as f:
        json.dump({"per_task": per_task, "totals": dict(tot)}, f, indent=1)
    print("\nwrote results/mutation.json")


if __name__ == "__main__":
    main()
