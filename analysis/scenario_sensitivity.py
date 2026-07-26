"""ITEM 32-part: leave-one-scenario-out sensitivity of the all-scenarios-pass verdict.

Interpreter-only (no nuXmv / no MATIEC). Uses the retained July open-panel
completions in results/frontier_n10/*.json (samples[].code) and the scan-cycle
interpreter (plcbench.st.interp) to score each candidate's scenarios individually.

For every task with >=2 scenarios and every sample:
  * score each scenario independently (parse once; a parse/runtime failure = that
    scenario fails, matching plcbench.backends.simulate semantics);
  * full verdict  = ALL scenarios pass;
  * for each scenario s, dropped verdict = ALL *other* scenarios pass.
A drop flips the verdict iff the sample fails EXACTLY that one scenario. (Dropping a
constraint can only turn a False verdict True, never the reverse.)

Aggregates reported:
  * per (task, dropped scenario): #samples whose all-pass verdict flips;
  * most-influential single scenario removal (max flips) and its denominator;
  * median flips over all drop events;
  * sanity: recomputed full verdict vs the stored samples[].scenario field.

Run:  wsl bash toolchain/wsl_analysis.sh analysis/scenario_sensitivity.py
Writes results/scenario_sensitivity.json
"""
from __future__ import annotations
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench.st import STSyntaxError
from plcbench.st.parser import parse_program
from plcbench.st.interp import check_scenarios

FRONTIER = "results/frontier_n10"
OUT = "results/scenario_sensitivity.json"


def per_scenario_pass(code: str, scenarios: list) -> list:
    """Return a list[bool] (one per scenario) of pass/fail under the interpreter.
    Parse failure -> all fail; a per-scenario runtime error -> that scenario fails."""
    try:
        prog = parse_program(code)
    except (STSyntaxError, Exception):  # noqa: BLE001
        return [False] * len(scenarios)
    out = []
    for sc in scenarios:
        try:
            res = check_scenarios(prog, [sc])  # [(id, ok, detail)]
            out.append(bool(res and res[0][1]))
        except Exception:  # noqa: BLE001 (interpreter runtime issue on this scenario)
            out.append(False)
    return out


def main() -> int:
    tasks = {lt.id: lt.task for lt in load_all()}
    files = sorted(glob.glob(os.path.join(FRONTIER, "*.json")))
    models = []
    # gather samples: task_id -> list of (model, code)
    by_task: dict[str, list] = {}
    total_samples = 0
    for fp in files:
        d = json.load(open(fp, encoding="utf-8"))
        if "rows" not in d:
            continue
        model = d.get("model_spec", os.path.basename(fp))
        models.append(model)
        for r in d["rows"]:
            tid = r["task_id"]
            for s in r["samples"]:
                code = s.get("code")
                total_samples += 1
                if code is None:
                    code = ""
                by_task.setdefault(tid, []).append(
                    {"model": model, "code": code,
                     "stored_scenario": s.get("scenario")})

    per_task = {}
    drop_events = []          # flat list of flip counts, one per (task, scenario)
    sanity_mismatch = 0
    sanity_checked = 0
    n_multi_samples = 0
    fail_exactly_one_total = 0
    dist = {"pass_all": 0, "fail_1": 0, "fail_2plus": 0}

    for tid, task in tasks.items():
        scenarios = task.scenarios
        nsc = len(scenarios)
        samples = by_task.get(tid, [])
        if nsc < 2:
            continue  # leave-one-out only defined for >=2 scenarios
        flips_per_scen = [0] * nsc
        n_here = 0
        for smp in samples:
            passv = per_scenario_pass(smp["code"], scenarios)
            n_passed = sum(passv)
            full_ok = (n_passed == nsc)
            n_here += 1
            n_multi_samples += 1
            # sanity vs stored (only meaningful when the stored verdict exists)
            if smp["stored_scenario"] is not None:
                sanity_checked += 1
                if bool(smp["stored_scenario"]) != full_ok:
                    sanity_mismatch += 1
            if full_ok:
                dist["pass_all"] += 1
            elif n_passed == nsc - 1:
                dist["fail_1"] += 1
            else:
                dist["fail_2plus"] += 1
            # a drop of scenario s flips iff the sample fails ONLY s
            if n_passed == nsc - 1 and not full_ok:
                failing = passv.index(False)
                flips_per_scen[failing] += 1
                fail_exactly_one_total += 1
        per_task[tid] = {
            "n_scenarios": nsc,
            "scenario_ids": [sc.id for sc in scenarios],
            "n_samples": n_here,
            "flips_per_dropped_scenario": {
                scenarios[i].id: flips_per_scen[i] for i in range(nsc)},
            "max_flips": max(flips_per_scen) if flips_per_scen else 0,
        }
        for i in range(nsc):
            drop_events.append({
                "task": tid, "scenario": scenarios[i].id,
                "flips": flips_per_scen[i], "n_samples": n_here})

    all_flip_counts = [e["flips"] for e in drop_events]
    most = max(drop_events, key=lambda e: e["flips"]) if drop_events else None

    result = {
        "note": "leave-one-scenario-out on frontier_n10 open panel; interpreter only",
        "models": models,
        "total_panel_samples": total_samples,
        "multi_scenario_tasks": sum(1 for t in tasks.values()
                                    if len(t.scenarios) >= 2),
        "single_scenario_tasks_excluded": sorted(
            t for t, tk in tasks.items() if len(tk.scenarios) < 2),
        "samples_on_multi_scenario_tasks": n_multi_samples,
        "verdict_distribution_multi": dist,
        "drop_events_total": len(drop_events),
        "flips_summary": {
            "most_influential": most,
            "max_flips": most["flips"] if most else 0,
            "median_flips_per_drop": statistics.median(all_flip_counts)
            if all_flip_counts else 0,
            "mean_flips_per_drop": round(statistics.mean(all_flip_counts), 3)
            if all_flip_counts else 0,
            "total_flips_over_all_drops": sum(all_flip_counts),
            "samples_failing_exactly_one_scenario": fail_exactly_one_total,
        },
        "sanity_recompute_vs_stored": {
            "checked": sanity_checked, "mismatches": sanity_mismatch},
        "per_task": per_task,
        "drop_events": sorted(drop_events, key=lambda e: -e["flips"]),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=1)

    print("== ITEM 32: scenario-count sensitivity (leave-one-scenario-out) ==")
    print("models:", models)
    print("total panel samples:", total_samples,
          "| on multi-scenario tasks:", n_multi_samples)
    print("multi-scenario tasks:", result["multi_scenario_tasks"],
          "| excluded (1 scenario):", result["single_scenario_tasks_excluded"])
    print("verdict dist (multi):", dist)
    print("sanity recompute vs stored samples[].scenario:",
          f"{sanity_mismatch} mismatches / {sanity_checked} checked")
    print("drop events (task,scenario pairs):", len(drop_events))
    if most:
        print(f"MOST influential drop: task={most['task']} scenario={most['scenario']}"
              f" -> {most['flips']} flips of {most['n_samples']} task samples"
              f" ({most['flips']}/{total_samples} of full panel)")
    print("median flips per drop:", result["flips_summary"]["median_flips_per_drop"])
    print("mean flips per drop:", result["flips_summary"]["mean_flips_per_drop"])
    print("total flips over all drops:",
          result["flips_summary"]["total_flips_over_all_drops"],
          "(= #samples failing exactly one scenario)")
    print("\nTop 12 drop events by flips:")
    for e in result["drop_events"][:12]:
        print(f"  {e['task']:32s} drop {e['scenario']:14s} flips={e['flips']:3d}"
              f"  /{e['n_samples']}")
    print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
