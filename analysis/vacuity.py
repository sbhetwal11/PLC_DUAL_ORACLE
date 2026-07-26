"""Per-property vacuity / obligation classification (DeepReview M22).

For every safety property, determine:
  - positive_obligation : the formula can force an OUTPUT variable to be TRUE
                          (i.e. a genuine "must act" requirement)
  - vacuous_under_alloff: satisfied by the all-outputs-FALSE (inert) controller
  - form                : guard->!out | mutual-exclusion | out->precond | positive | other

Pure static analysis over the LTL text + interface directions; no harness needed.
"""
from __future__ import annotations
import json, glob, os, re, itertools
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "benchmark", "tasks")


def strip_g(ltl):
    b = ltl.strip()
    if b.startswith("G(") and b.endswith(")"):
        return b[2:-1]
    return b


def eval_phi(phi, env):
    s = phi
    s = s.replace("->", " __IMP__ ").replace("&", " and ").replace("|", " or ")
    s = re.sub(r"!\s*", " not ", s)
    s = re.sub(r"X\s*\(", "(", s)

    def impl(e):
        if "__IMP__" in e:
            i = e.rindex("__IMP__")
            return (not atom(e[:i])) or impl(e[i + 7:])
        return atom(e)

    def atom(e):
        e = e.strip()
        return bool(eval(e, {"__builtins__": {}}, env))
    return impl(s)


def domain(v):
    if v.get("type") == "INT":
        r = v.get("range") or [0, 100]
        lo, hi = int(r[0]), int(r[1])
        pts = sorted(set([lo, hi, (lo + hi) // 2, min(hi, 10), min(hi, 90), max(lo, 3)]))
        return [p for p in pts if lo <= p <= hi]
    return [0, 1]


def positive_obligation(phi, outs):
    """True if some assignment forces an output TRUE for the formula to hold,
    i.e. the property is NOT satisfiable with all outputs FALSE for some input."""
    # detected empirically below via vacuity: a property is a positive obligation
    # iff all-off can violate it (there exists an input making it false when outputs=0).
    return None


def main():
    metas = glob.glob(os.path.join(ROOT, "**", "meta.json"), recursive=True)
    order = {"easy": 0, "medium": 1, "hard": 2}
    tasks = []
    for m in metas:
        d = json.load(open(m, encoding="utf-8"))
        outs = [v["name"] for v in d["interface"] if v["direction"] == "output"]
        ins = [v for v in d["interface"] if v["direction"] == "input"]
        tasks.append((order[d["difficulty"]], d["id"], outs, ins, d.get("safety_properties", [])))
    tasks.sort()

    rows = []
    counts = defaultdict(int)
    for _, tid, outs, ins, props in tasks:
        for p in props:
            ltl = p.get("ltl", "")
            if not ltl:
                continue
            phi = strip_g(ltl)
            refset = set(re.findall(r"[A-Za-z_]\w*", phi)) - {"X", "G", "F", "U"}
            innames = {v["name"] for v in ins}
            internal = [r for r in refset if r not in outs and r not in innames]
            invars = [v for v in ins if v["name"] in refset]
            doms = [domain(v) for v in invars]
            # vacuous under all-off: outputs=0, internal=0, over all input combos
            vac = True
            for combo in (itertools.product(*doms) if invars else [()]):
                env = {o: False for o in outs}
                env.update({n: 0 for n in internal})
                for v, val in zip(invars, combo):
                    env[v["name"]] = val
                try:
                    if not eval_phi(phi, env):
                        vac = False
                        break
                except Exception:
                    vac = None
                    break
            # positive obligation == NOT vacuous under all-off (all-off can violate it)
            pos = (vac is False)
            # form
            mentions_out = any(o in refset for o in outs)
            neg_out = any(re.search(rf"!\s*{re.escape(o)}", phi) for o in outs)
            if not mentions_out:
                form = "input-only"
            elif "&" in phi and "!" in phi and "->" not in phi:
                form = "mutual-exclusion"
            elif pos:
                form = "positive-obligation"
            elif neg_out and "->" in phi:
                form = "guard->!out"
            else:
                form = "other"
            counts[form] += 1
            counts["vacuous_alloff" if vac else "nonvacuous_alloff"] += 1
            if pos:
                counts["positive_total"] += 1
            rows.append((tid, p.get("id", "?"), form, vac, pos, ltl))

    print("# Per-property vacuity / obligation analysis\n")
    print(f"{'task':28s} {'prop':6s} {'form':20s} {'vac_alloff':10s} {'positive':8s}  LTL")
    for tid, pid, form, vac, pos, ltl in rows:
        print(f"{tid:28s} {pid:6s} {form:20s} {str(vac):10s} {str(pos):8s}  {ltl}")
    total = len(rows)
    print(f"\n## Totals ({total} properties)")
    print(f"   vacuously satisfied by all-off:   {counts['vacuous_alloff']}  ({counts['vacuous_alloff']/total:.3f})")
    print(f"   NOT vacuous (all-off violates):   {counts['nonvacuous_alloff']}  ({counts['nonvacuous_alloff']/total:.3f})")
    print(f"   positive-output obligations:      {counts['positive_total']}")
    print("   forms:", {k: counts[k] for k in ['guard->!out','mutual-exclusion','positive-obligation','other','input-only'] if counts[k]})
    with open("results/vacuity.json", "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "counts": dict(counts)}, f, indent=1, default=str)
    print("\nwrote results/vacuity.json")


if __name__ == "__main__":
    main()
