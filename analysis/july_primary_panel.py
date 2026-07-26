"""DELIVERABLE 1 (final-revision round): promote the July n=10 API panel to the
PRIMARY RQ1/RQ3/RQ4 table (June becomes supplementary replication).

Source: results/frontier_n10/{grok_grok-3, anthropic_claude-sonnet-4-6,
gemini_gemini-2.5-flash, openai_gpt-4o}.json -- 22 tasks x 10 samples/model.
Per sample: code/compile/invariant/scenario/taskvalid; per-row counters
c_compile / c_verified / c_scenario / c_taskvalid.

Field semantics (from analysis/api_panel_n10.py::score + plcbench/harness.evaluate):
  compile   = MATIEC accepts the program                       -> c_compile
  invariant = ev.verified = (compiles is not False) AND all safety props hold
              i.e. COMPILE-AND-INVARIANT (the RQ1/RQ3 headline)-> c_verified
  scenario  = every reference scenario passes                  -> c_scenario
  taskvalid = compile AND invariant AND scenario (ALL-CHECKS)  -> c_taskvalid

Produces results/july_primary_panel.json with, per model:
 (a) compile-and-invariant pass@1/pass@10 overall AND per tier (E*=easy 7,
     M*=medium 11, H*=hard 4), unbiased Chen et al. estimator averaged over tasks;
 (b) the 22-row per-task matrix of c_verified and c_taskvalid;
 (c) all-checks-pass pass@1/pass@10 overall+per tier, cross-checked vs the paper's
     Table II (tab:taskvalid) -- any mismatch REPORTED;
 (d) FAILURE TAXONOMY over all 880 stored programs: re-run the harness categorizer
     (plcbench/generate/evaluate._categorize) -> parse_error / compile_error /
     translate_error / unsafe / verified / unknown(timeout); per-model counts +
     the "unsafe" count (RQ4 needs: who emits MATIEC-accepted invariant-violating
     programs, and how many). Recomputed 'verified' cross-checked vs stored c_verified.
 (e) RQ3: per-model easy/medium/hard compile-and-invariant pass@1 (subset of (a)).

Then prints a July-vs-June claim-survival block for every headline sentence and
FLAGS any June-based claim that flips under July.

Run: wsl bash toolchain/wsl_analysis.sh analysis/july_primary_panel.py
"""
from __future__ import annotations
import json, math, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness
from plcbench.generate.evaluate import _categorize
from plcbench.st import STSyntaxError, parse_program

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "july_primary_panel.json")
FRONTIER = os.path.join(ROOT, "results", "frontier_n10")

# file -> canonical display key (kept parallel to the paper's row order)
MODELS = [
    ("grok",   "grok_grok-3.json",                "grok-4.3 (grok-3 slug)"),
    ("claude", "anthropic_claude-sonnet-4-6.json", "claude-sonnet-4-6"),
    ("gemini", "gemini_gemini-2.5-flash.json",     "gemini-2.5-flash"),
    ("gpt-4o", "openai_gpt-4o.json",               "gpt-4o"),
]
TIERS = {"E": "easy", "M": "medium", "H": "hard"}
TIER_ORDER = ["easy", "medium", "hard"]

# ---- JUNE reference (main.tex Table I / tab:main) : compile-and-invariant --------
JUNE_CI = {
    "grok":   {"p1": 0.645, "easy": 0.857, "medium": 0.536, "hard": 0.575, "p10": 0.955, "smv": 0.745},
    "claude": {"p1": 0.564, "easy": 1.000, "medium": 0.318, "hard": 0.475, "p10": 0.682, "smv": 0.591},
    "gemini": {"p1": 0.095, "easy": 0.200, "medium": 0.000, "hard": 0.175, "p10": 0.273, "smv": 0.155},
    "gpt-4o": {"p1": 0.091, "easy": 0.157, "medium": 0.082, "hard": 0.000, "p10": 0.227, "smv": 0.295},
}
# ---- Paper's EXISTING July numbers (main.tex Table II / tab:taskvalid) -----------
# columns: MATIEC-accepted(compile) | compile+invariant | scenario | all-checks(taskvalid) p1 | p10
PAPER_JULY = {
    "grok":   {"compile": 0.895, "ci": 0.677, "scenario": 0.673, "tv1": 0.591, "tv10": 0.909},
    "claude": {"compile": 0.923, "ci": 0.555, "scenario": 0.473, "tv1": 0.459, "tv10": 0.500},
    "gemini": {"compile": 0.127, "ci": 0.100, "scenario": 0.200, "tv1": 0.100, "tv10": 0.273},
    "gpt-4o": {"compile": 0.141, "ci": 0.109, "scenario": 0.286, "tv1": 0.095, "tv10": 0.364},
}
TOL = 0.006  # rounding tolerance for 3-dp paper values


def passk_from_counts(rows, field, k):
    """Unbiased pass@k (Chen et al.) averaged over tasks. Identical to
    analysis/verify_docs13.py::passk_from_counts."""
    vals = []
    for r in rows:
        n = r["n"]; c = r.get(field, 0)
        if k > n:
            vals.append(1.0 if c > 0 else 0.0); continue
        if c == 0:
            vals.append(0.0)
        elif c >= n:
            vals.append(1.0)
        else:
            vals.append(1.0 - math.comb(n - c, k) / math.comb(n, k))
    return sum(vals) / len(vals) if vals else 0.0


def tier_of(task_id):
    return TIERS[task_id[0]]


def load_rows(fname):
    """Return list of {task_id, tier, n, c_verified, c_taskvalid, c_compile,
    c_scenario, samples} for one model."""
    doc = json.load(open(os.path.join(FRONTIER, fname), encoding="utf-8"))
    rows = []
    for r in doc["rows"]:
        n = len(r["samples"])
        rows.append({
            "task_id": r["task_id"], "tier": tier_of(r["task_id"]), "n": n,
            "c_compile": r["c_compile"], "c_verified": r["c_verified"],
            "c_scenario": r["c_scenario"], "c_taskvalid": r["c_taskvalid"],
            "samples": r["samples"],
        })
    return rows, doc


def passk_block(rows, field):
    """pass@1/pass@10 overall + per tier for a given per-task count field."""
    out = {"overall": {"pass@1": passk_from_counts(rows, field, 1),
                       "pass@10": passk_from_counts(rows, field, 10)}}
    for tier in TIER_ORDER:
        tr = [r for r in rows if r["tier"] == tier]
        out[tier] = {"n_tasks": len(tr),
                     "pass@1": passk_from_counts(tr, field, 1),
                     "pass@10": passk_from_counts(tr, field, 10)}
    return out


def taxonomy(rows, by_id):
    """Re-run the harness categorizer over every stored program.
    Returns (counts dict, n_verified_recomputed, unsafe_task_detail list)."""
    cats = {}
    n_verified = 0
    unsafe_detail = []
    for r in rows:
        lt = by_id.get(r["task_id"])
        if lt is None:  # tolerate id suffix drift
            lt = next((v for k, v in by_id.items()
                       if k.startswith(r["task_id"]) or r["task_id"].startswith(k)), None)
        for s in r["samples"]:
            code = s.get("code") or ""
            ev = harness.evaluate(lt.task, code)
            try:
                parse_program(code); parsed = True
            except (STSyntaxError, Exception):
                parsed = False
            cat = _categorize(parsed, ev)
            cats[cat] = cats.get(cat, 0) + 1
            if cat == "verified":
                n_verified += 1
            if cat == "unsafe":
                statuses = [p.status for p in ev.verify.properties] if ev.verify else []
                unsafe_detail.append({
                    "task_id": r["task_id"], "tier": r["tier"], "i": s.get("i"),
                    "n_props": len(statuses),
                    "n_fail": sum(1 for x in statuses if x == "fail"),
                    "n_pass": sum(1 for x in statuses if x == "pass"),
                })
    return cats, n_verified, unsafe_detail


def fmt(x):
    return f"{x:.3f}" if isinstance(x, float) else str(x)


def main():
    t_start = time.time()
    by_id = {lt.task.id: lt for lt in load_all()}

    results = {
        "window": "July 2026 (retained raw completions, results/frontier_n10/*)",
        "n_per_task": 10, "n_tasks": 22, "tiers": {"easy": 7, "medium": 11, "hard": 4},
        "estimator": "unbiased Chen et al. pass@k, averaged over tasks",
        "field_semantics": {
            "compile_and_invariant": "c_verified (per-sample 'invariant' = harness.verified)",
            "all_checks_pass": "c_taskvalid (compile AND invariant AND scenario)"},
        "models": {}, "cross_checks": {}, "comparison_june_vs_july": {},
    }

    model_rows = {}
    for key, fname, disp in MODELS:
        rows, doc = load_rows(fname)
        model_rows[key] = rows
        ci = passk_block(rows, "c_verified")          # (a) compile-and-invariant
        tv = passk_block(rows, "c_taskvalid")         # (c) all-checks-pass
        cp = passk_block(rows, "c_compile")           # constituent: MATIEC-accepted
        sc = passk_block(rows, "c_scenario")          # constituent: scenario
        matrix = [{"task_id": r["task_id"], "tier": r["tier"],
                   "c_verified": r["c_verified"], "c_taskvalid": r["c_taskvalid"],
                   "c_compile": r["c_compile"], "c_scenario": r["c_scenario"]}
                  for r in rows]                        # (b) 22-row matrix
        results["models"][key] = {
            "display": disp, "source_file": fname,
            "compile_and_invariant": ci,               # (a)
            "all_checks_pass": tv,                     # (c)
            "matiec_accepted": cp, "scenario": sc,
            "per_task_matrix": matrix,                  # (b)
            "rq3_ci_pass1_by_tier": {t: ci[t]["pass@1"] for t in TIER_ORDER},  # (e)
        }

    # ---------- (d) FAILURE TAXONOMY over all 880 programs -----------------------
    print("== (d) Re-running harness categorizer over 880 stored programs ==", flush=True)
    for key, fname, disp in MODELS:
        t0 = time.time()
        cats, n_ver, unsafe_detail = taxonomy(model_rows[key], by_id)
        total = sum(cats.values())
        stored_ver = sum(r["c_verified"] for r in model_rows[key])
        results["models"][key]["failure_taxonomy"] = {
            "total_samples": total, "categories": cats,
            "unsafe_count": cats.get("unsafe", 0),
            "unsafe_detail": unsafe_detail,
            "recomputed_verified": n_ver, "stored_c_verified": stored_ver,
            "verified_matches_stored": (n_ver == stored_ver),
        }
        flag = "" if n_ver == stored_ver else "  <-- MISMATCH vs stored!"
        print(f"  {disp:26s} {json.dumps(cats)}  unsafe={cats.get('unsafe',0)} "
              f"| recomp_verified={n_ver} stored={stored_ver}{flag}  "
              f"({time.time()-t0:.1f}s)", flush=True)

    # ---------- cross-checks vs paper Table II (July) ---------------------------
    print("\n== cross-check: computed vs paper Table II (tab:taskvalid, July) ==", flush=True)
    xc = results["cross_checks"]
    for key, fname, disp in MODELS:
        m = results["models"][key]
        comp = {
            "compile_and_invariant_pass1": (m["compile_and_invariant"]["overall"]["pass@1"], PAPER_JULY[key]["ci"]),
            "all_checks_pass_pass1":        (m["all_checks_pass"]["overall"]["pass@1"], PAPER_JULY[key]["tv1"]),
            "all_checks_pass_pass10":       (m["all_checks_pass"]["overall"]["pass@10"], PAPER_JULY[key]["tv10"]),
            "matiec_accepted_pass1":        (m["matiec_accepted"]["overall"]["pass@1"], PAPER_JULY[key]["compile"]),
            "scenario_pass1":               (m["scenario"]["overall"]["pass@1"], PAPER_JULY[key]["scenario"]),
        }
        rec = {}
        for metric, (got, paper) in comp.items():
            ok = abs(got - paper) <= TOL
            rec[metric] = {"computed": round(got, 4), "paper": paper,
                           "delta": round(got - paper, 4), "match": ok}
            tag = "OK  " if ok else "MISMATCH"
            print(f"  {disp:26s} {metric:30s} computed {got:.3f} paper {paper:.3f} "
                  f"d={got-paper:+.3f} [{tag}]")
        xc[key] = rec

    # ---------- (a)/(e) print July per-tier compile-and-invariant ---------------
    print("\n== (a)/(e) JULY compile-and-invariant pass@1 by tier (RQ1/RQ3) ==", flush=True)
    print(f"  {'model':26s} {'overall':>8s} {'easy':>7s} {'medium':>7s} {'hard':>7s} {'p@10':>7s}")
    for key, fname, disp in MODELS:
        ci = results["models"][key]["compile_and_invariant"]
        print(f"  {disp:26s} {ci['overall']['pass@1']:8.3f} {ci['easy']['pass@1']:7.3f} "
              f"{ci['medium']['pass@1']:7.3f} {ci['hard']['pass@1']:7.3f} "
              f"{ci['overall']['pass@10']:7.3f}")

    # ---------- JULY-vs-JUNE comparison + FLIP FLAGS ----------------------------
    print("\n" + "=" * 78)
    print("JULY vs JUNE  (compile-and-invariant; June = main.tex Table I / tab:main)")
    print("=" * 78)
    cmp = results["comparison_june_vs_july"]

    # leader order at pass@1
    def order(getter):
        return [k for k, _, _ in sorted(MODELS, key=lambda mm: -getter(mm[0]))]
    july_p1 = lambda k: results["models"][k]["compile_and_invariant"]["overall"]["pass@1"]
    june_p1 = lambda k: JUNE_CI[k]["p1"]
    july_order = order(july_p1)
    june_order = order(june_p1)
    cmp["leader_order_pass1"] = {
        "june": june_order, "july": july_order,
        "changed": june_order != july_order}
    print(f"\n[leader order @pass1]  June: {' > '.join(june_order)}")
    print(f"                       July: {' > '.join(july_order)}")
    if june_order != july_order:
        print("  *** FLAG: leader ORDER changes between June and July ***")
    else:
        print("  order preserved.")

    # per-model per-tier table + flips
    print("\n[per-model overall + per-tier pass@1 and pass@10]")
    cmp["per_model"] = {}
    for key, fname, disp in MODELS:
        ci = results["models"][key]["compile_and_invariant"]
        j = JUNE_CI[key]
        rec = {"overall_pass1": {"june": j["p1"], "july": round(ci["overall"]["pass@1"], 4)},
               "overall_pass10": {"june": j["p10"], "july": round(ci["overall"]["pass@10"], 4)},
               "easy_pass1": {"june": j["easy"], "july": round(ci["easy"]["pass@1"], 4)},
               "medium_pass1": {"june": j["medium"], "july": round(ci["medium"]["pass@1"], 4)},
               "hard_pass1": {"june": j["hard"], "july": round(ci["hard"]["pass@1"], 4)}}
        cmp["per_model"][key] = rec
        print(f"\n  {disp}")
        for tk, lbl in [("overall_pass1", "overall p@1"), ("overall_pass10", "overall p@10"),
                        ("easy_pass1", "easy p@1"), ("medium_pass1", "medium p@1"),
                        ("hard_pass1", "hard p@1")]:
            ju, jl = rec[tk]["june"], rec[tk]["july"]
            print(f"    {lbl:14s} June {ju:.3f}  July {jl:.3f}  d={jl-ju:+.3f}")

    # tier-wall claims (June): gpt-4o hard=0 ; gemini medium=0
    print("\n[tier-wall claims from June]")
    walls = {}
    gpt_hard_july = results["models"]["gpt-4o"]["compile_and_invariant"]["hard"]["pass@1"]
    gem_med_july = results["models"]["gemini"]["compile_and_invariant"]["medium"]["pass@1"]
    # 'at any k': also check pass@10
    gpt_hard_july10 = results["models"]["gpt-4o"]["compile_and_invariant"]["hard"]["pass@10"]
    gem_med_july10 = results["models"]["gemini"]["compile_and_invariant"]["medium"]["pass@10"]
    walls["gpt4o_hard_zero"] = {"june_pass1": 0.000, "july_pass1": round(gpt_hard_july, 4),
                                "july_pass10": round(gpt_hard_july10, 4),
                                "holds": gpt_hard_july == 0.0 and gpt_hard_july10 == 0.0}
    walls["gemini_medium_zero"] = {"june_pass1": 0.000, "july_pass1": round(gem_med_july, 4),
                                   "july_pass10": round(gem_med_july10, 4),
                                   "holds": gem_med_july == 0.0 and gem_med_july10 == 0.0}
    cmp["tier_walls"] = walls
    print(f"  gpt-4o hard=0 (any k):  July p@1={gpt_hard_july:.3f} p@10={gpt_hard_july10:.3f}  "
          f"-> {'HOLDS' if walls['gpt4o_hard_zero']['holds'] else '*** FLAG: BROKEN ***'}")
    print(f"  gemini medium=0 (any k):July p@1={gem_med_july:.3f} p@10={gem_med_july10:.3f}  "
          f"-> {'HOLDS' if walls['gemini_medium_zero']['holds'] else '*** FLAG: BROKEN ***'}")

    # claude-flat-vs-grok-climbing pass@1 -> pass@10
    print("\n[claude flat vs grok climbing, pass@1 -> pass@10]")
    cg = {}
    for key in ("grok", "claude"):
        ci = results["models"][key]["compile_and_invariant"]["overall"]
        cg[key] = {"june": (JUNE_CI[key]["p1"], JUNE_CI[key]["p10"]),
                   "july": (round(ci["pass@1"], 4), round(ci["pass@10"], 4)),
                   "july_gain": round(ci["pass@10"] - ci["pass@1"], 4),
                   "june_gain": round(JUNE_CI[key]["p10"] - JUNE_CI[key]["p1"], 4)}
    cmp["flat_vs_climbing"] = cg
    for key in ("grok", "claude"):
        d = cg[key]
        print(f"  {key:7s} June {d['june'][0]:.3f}->{d['june'][1]:.3f} (gain {d['june_gain']:+.3f})"
              f"  July {d['july'][0]:.3f}->{d['july'][1]:.3f} (gain {d['july_gain']:+.3f})")
    contrast_holds = cg["grok"]["july_gain"] > cg["claude"]["july_gain"]
    cmp["flat_vs_climbing"]["contrast_holds"] = contrast_holds
    print(f"  grok climbs more than claude under July: "
          f"{'HOLDS' if contrast_holds else '*** FLAG: BROKEN ***'}")

    # RQ3 easy>medium wall (claude easy 1.000 vs medium 0.318 in June)
    print("\n[RQ3: timed/sequential harder than combinational -- claude easy vs medium]")
    cl = results["models"]["claude"]["compile_and_invariant"]
    rq3 = {"claude_easy_pass1": {"june": 1.000, "july": round(cl["easy"]["pass@1"], 4)},
           "claude_medium_pass1": {"june": 0.318, "july": round(cl["medium"]["pass@1"], 4)}}
    rq3["easy_gt_medium_all_models"] = {
        k: {"easy": round(results["models"][k]["compile_and_invariant"]["easy"]["pass@1"], 4),
            "medium": round(results["models"][k]["compile_and_invariant"]["medium"]["pass@1"], 4),
            "hard": round(results["models"][k]["compile_and_invariant"]["hard"]["pass@1"], 4)}
        for k in ("grok", "claude", "gemini", "gpt-4o")}
    cmp["rq3"] = rq3
    print(f"  claude easy  June 1.000  July {cl['easy']['pass@1']:.3f}")
    print(f"  claude medium June 0.318  July {cl['medium']['pass@1']:.3f}")
    print(f"  easy>=medium holds for claude under July: "
          f"{'YES' if cl['easy']['pass@1'] >= cl['medium']['pass@1'] else '*** FLAG: NO ***'}")

    results["runtime_sec"] = round(time.time() - t_start, 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print(f"\nwrote {OUT}  ({results['runtime_sec']}s)")


if __name__ == "__main__":
    main()
