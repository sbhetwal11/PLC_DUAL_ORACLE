"""Task-valid metric + orthogonal taxonomy for the API panel (DeepReview B1, M9, M23, M29).

Re-evaluates each model's saved single-sample program with the real harness and
reports four *separate* dimensions plus a combined task-valid rate:

  compile    : MATIEC accepts and translates
  invariant  : compile AND all safety properties hold (nuXmv)  [the old 'verified-safe']
  scenario   : all execution scenarios pass (interpreter)
  task-valid : compile AND invariant AND scenario

Also records the orthogonal taxonomy (M9): independent Extraction / MATIEC /
Translator / nuXmv fields, so a single precedence bucket does not hide which oracle failed.

Run under the WSL harness. Single sample per task (n=1); the n=10 pass@k programs
were not cached, so this is the n=1 panel (same run the appendix already used).
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness

MODELS = {
    "grok-3(dagger)": "results/grok_grok-3.json",
    "claude-sonnet-4-6": "results/anthropic_claude-sonnet-4-6.json",
    "gemini-2.5-flash": "results/gemini_gemini-2.5-flash.json",
    "gpt-4o": "results/openai_gpt-4o.json",
}


def load_tasks_by_id():
    return {lt.task.id: lt for lt in load_all()}


def orthostatus(ev):
    # Extraction: did we have a program at all
    extraction = "found" if ev.verify is not None or ev.compiles is not None else "not_found"
    matiec = {True: "accepted", False: "rejected", None: "n/a"}[ev.compiles]
    # translator/nuXmv from verify result
    if ev.verify is None or not ev.verify.available:
        translator = "n/a"; nuxmv = "not_run"
    else:
        st = ev.verify.status if hasattr(ev.verify, "status") else ""
        # infer translator support from whether an SMV model was produced
        translator = "supported" if ev.n_props > 0 and ev.verify.properties else "unsupported/error"
        if ev.n_props_pass == ev.n_props and ev.n_props > 0:
            nuxmv = "all_hold"
        elif ev.n_props > 0:
            nuxmv = "some_fail"
        else:
            nuxmv = "not_run"
    return extraction, matiec, translator, nuxmv


def main():
    by_id = load_tasks_by_id()
    order = {"easy": 0, "medium": 1, "hard": 2}
    out = {}
    print("# Task-valid panel (n=1 saved programs, re-scored by the real harness)\n")

    # reference sanity
    refc = refi = refs = reftv = 0
    for tid, lt in by_id.items():
        ev = harness.evaluate(lt.task, lt.reference_st)
        refc += ev.compiles is True
        refi += ev.verified is True
        refs += (ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total)
        reftv += (ev.compiles is True and ev.verified is True and
                  ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total)
    n = len(by_id)
    print(f"## reference solutions (sanity): compile {refc}/{n}  invariant {refi}/{n}  scenario {refs}/{n}  task-valid {reftv}/{n}\n")

    for model, path in MODELS.items():
        if not os.path.exists(path):
            print(f"## {model}: MISSING {path}\n"); continue
        d = json.load(open(path, encoding="utf-8"))
        rows = d["rows"]
        agg = defaultdict(int)
        taxo = defaultdict(lambda: defaultdict(int))
        range_rejects = []
        per = []
        for r in rows:
            tid = r["task_id"]
            lt = by_id.get(tid)
            if lt is None:
                # match by prefix
                lt = next((v for k, v in by_id.items() if k.startswith(tid) or tid.startswith(k)), None)
            code = r.get("code") or ""
            if lt is None or not code.strip():
                agg["no_program"] += 1
                continue
            ev = harness.evaluate(lt.task, code)
            c = ev.compiles is True
            i = ev.verified is True
            s = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
            tv = c and i and s
            agg["compile"] += c; agg["invariant"] += i; agg["scenario"] += s; agg["taskvalid"] += tv
            ext, mat, tr, nx = orthostatus(ev)
            taxo["extraction"][ext] += 1
            taxo["matiec"][mat] += 1
            taxo["translator"][tr] += 1
            taxo["nuxmv"][nx] += 1
            # integer-range rejection: translator rejected but MATIEC accepted
            if mat == "accepted" and tr.startswith("unsupported"):
                range_rejects.append(tid)
            per.append((lt.task.difficulty.value, tid, c, i, s, tv))
        m = len(rows)
        print(f"## {model}  (n={m} tasks, single sample)")
        print(f"   compile    {agg['compile']}/{m} = {agg['compile']/m:.3f}")
        print(f"   invariant  {agg['invariant']}/{m} = {agg['invariant']/m:.3f}   (old 'verified-safe')")
        print(f"   scenario   {agg['scenario']}/{m} = {agg['scenario']/m:.3f}")
        print(f"   TASK-VALID {agg['taskvalid']}/{m} = {agg['taskvalid']/m:.3f}")
        print(f"   orthogonal taxonomy: MATIEC={dict(taxo['matiec'])}  translator={dict(taxo['translator'])}  nuXmv={dict(taxo['nuxmv'])}")
        print(f"   translator-rejected-but-MATIEC-accepted (range/subset): {len(range_rejects)} {range_rejects}")
        print()
        out[model] = {"compile": agg["compile"], "invariant": agg["invariant"],
                      "scenario": agg["scenario"], "taskvalid": agg["taskvalid"], "n": m,
                      "taxonomy": {k: dict(v) for k, v in taxo.items()},
                      "range_rejects": range_rejects, "per_task": per}
    out["_reference"] = {"compile": refc, "invariant": refi, "scenario": refs, "taskvalid": reftv, "n": n}
    with open("results/taskvalid.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    print("wrote results/taskvalid.json")


if __name__ == "__main__":
    main()
