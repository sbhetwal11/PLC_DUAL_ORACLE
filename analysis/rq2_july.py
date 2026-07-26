"""ITEM 18 (round-16): reproduce the RQ2 inflation metric on the RETAINED July n=10
panel (results/frontier_n10/*.json), so the integrator can swap the June headline
(0.204 abs / 3.2x, gpt-4o) for a July number computed on released raw programs.

EXACT ORIGINAL METRIC (June; toolchain/wsl_passk_nuxmvonly.sh + docs/07 RQ2 table):
  - "safety-only" = translator+nuXmv model-check pass WITHOUT the MATIEC compile gate
    (the June nuXmv-only run literally `unset MATIEC_IEC2C`). Scenarios NOT included.
  - "compile-and-invariant" (dual oracle) = MATIEC compile AND all safety props hold.
  - inflation = safety-only overstates compile-and-invariant; report abs diff and ratio.

The July per-sample `invariant` field CANNOT be reused for safety-only because the
harness gates it on compile (harness.evaluate: verified = (compiles is not False) and
n_pass==n_props). So we recompute the UNGATED nuXmv verdict here by translating each
completion and model-checking every property regardless of MATIEC.

pass@k = unbiased Chen et al. estimator averaged over tasks (identical to
analysis/verify_docs13.py::passk_from_counts).

Run: wsl bash toolchain/wsl_analysis.sh analysis/rq2_july.py
"""
from __future__ import annotations
import glob, json, math, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench.backends import compile_matiec, verify_nuxmv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "rq2_july.json")
FILES = {
    "grok-4.3(grok-3 slug)": "grok_grok-3.json",
    "claude-sonnet-4-6":     "anthropic_claude-sonnet-4-6.json",
    "gemini-2.5-flash":      "gemini_gemini-2.5-flash.json",
    "gpt-4o":                "openai_gpt-4o.json",
}
# June counterparts from docs/07 RQ2 table + results/passk_nuxmvonly_*.json (historical).
JUNE = {
    "grok-4.3(grok-3 slug)": {"safety_only": 0.745, "compile_invariant": 0.645},
    "claude-sonnet-4-6":     {"safety_only": 0.591, "compile_invariant": 0.564},
    "gemini-2.5-flash":      {"safety_only": 0.155, "compile_invariant": 0.095},
    "gpt-4o":                {"safety_only": 0.295, "compile_invariant": 0.091},
}


def passk_from_counts(rows, field, k):
    """Unbiased pass@k over tasks from per-task counts of 'field' out of n."""
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


def score_sample(task, code):
    """Return (compile_ok, nuxmv_all_pass_UNGATED). nuxmv_all_pass ignores compile."""
    if not code or not code.strip():
        return False, False
    cres = compile_matiec.compile_st(code)
    compile_ok = bool(cres.ok) if cres.available else False
    vres = verify_nuxmv.verify(task, code)  # translator+nuXmv, independent of MATIEC
    if not vres.available or not vres.properties:
        nuxmv_all_pass = False
    else:
        nuxmv_all_pass = all(p.status == "pass" for p in vres.properties)
    return compile_ok, nuxmv_all_pass


def main():
    by_id = {lt.task.id: lt for lt in load_all()}
    frontier = os.path.join(ROOT, "results", "frontier_n10")
    results = {"metric": "RQ2 inflation: safety-only (ungated nuXmv) vs "
                         "compile-and-invariant (dual oracle); scenarios excluded",
               "window": "July 2026 (retained raw completions)",
               "per_model": {}, "pooled": {}, "june": JUNE}
    pooled_rows_safety, pooled_rows_ci = [], []
    n_total = 0
    for model, fname in FILES.items():
        path = os.path.join(frontier, fname)
        doc = json.load(open(path, encoding="utf-8"))
        rows = []
        for row in doc["rows"]:
            tid = row["task_id"]
            lt = by_id.get(tid)
            if lt is None:
                lt = next((v for k, v in by_id.items()
                           if k.startswith(tid) or tid.startswith(k)), None)
            c_safety = c_ci = 0
            n = 0
            for s in row["samples"]:
                n += 1; n_total += 1
                comp, nux = score_sample(lt.task, s.get("code") or "")
                c_safety += 1 if nux else 0
                c_ci += 1 if (comp and nux) else 0
            rr = {"task_id": tid, "difficulty": row["difficulty"], "n": n,
                  "c_safety": c_safety, "c_ci": c_ci,
                  "c_verified_stored": row.get("c_verified")}
            rows.append(rr)
            print(f"  {model:26s} {tid:32s} safety {c_safety}/{n}  ci {c_ci}/{n} "
                  f"(stored inv {row.get('c_verified')})", flush=True)
        so1 = passk_from_counts(rows, "c_safety", 1)
        ci1 = passk_from_counts(rows, "c_ci", 1)
        so10 = passk_from_counts(rows, "c_safety", 10)
        ci10 = passk_from_counts(rows, "c_ci", 10)
        ci1_stored = passk_from_counts(
            [{"n": r["n"], "c": r["c_verified_stored"] or 0} for r in rows], "c", 1)
        results["per_model"][model] = {
            "rows": rows,
            "safety_only_pass1": so1, "compile_invariant_pass1": ci1,
            "abs_diff_pass1": so1 - ci1,
            "ratio_pass1": (so1 / ci1) if ci1 else None,
            "safety_only_pass10": so10, "compile_invariant_pass10": ci10,
            "abs_diff_pass10": so10 - ci10,
            "compile_invariant_pass1_stored": ci1_stored,
        }
        pooled_rows_safety.extend(rows)
        pooled_rows_ci.extend(rows)
        print(f"== {model}: safety@1 {so1:.3f} ci@1 {ci1:.3f} "
              f"abs {so1-ci1:.3f} ratio {(so1/ci1 if ci1 else float('nan')):.2f} "
              f"| safety@10 {so10:.3f} ci@10 {ci10:.3f}", flush=True)

    pso1 = passk_from_counts(pooled_rows_safety, "c_safety", 1)
    pci1 = passk_from_counts(pooled_rows_ci, "c_ci", 1)
    pso10 = passk_from_counts(pooled_rows_safety, "c_safety", 10)
    pci10 = passk_from_counts(pooled_rows_ci, "c_ci", 10)
    results["pooled"] = {
        "n_rows": len(pooled_rows_safety), "n_samples": n_total,
        "safety_only_pass1": pso1, "compile_invariant_pass1": pci1,
        "abs_diff_pass1": pso1 - pci1, "ratio_pass1": (pso1 / pci1) if pci1 else None,
        "safety_only_pass10": pso10, "compile_invariant_pass10": pci10,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print("\n==== SUMMARY (July) ====")
    for m, d in results["per_model"].items():
        print(f"{m:26s} safety@1 {d['safety_only_pass1']:.3f} "
              f"ci@1 {d['compile_invariant_pass1']:.3f} "
              f"abs {d['abs_diff_pass1']:.3f} "
              f"ratio {d['ratio_pass1'] if d['ratio_pass1'] else float('nan'):.2f} "
              f"(ci@1 stored {d['compile_invariant_pass1_stored']:.3f})")
    print(f"POOLED safety@1 {pso1:.3f} ci@1 {pci1:.3f} abs {pso1-pci1:.3f} "
          f"ratio {(pso1/pci1 if pci1 else float('nan')):.2f}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
