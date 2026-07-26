"""DELIVERABLE 2 (final-revision round): SEVEN-TASK EXCLUSION SENSITIVITY.

Author-side expert review flagged 7 tasks with blocking property gaps:
  E03_airlock_interlock, M02_star_delta_starter, M03_pedestrian_crossing,
  M06_burner_purge_sequence, M07_two_hand_control, H03_batch_reactor_sequence,
  H04_parking_garage_counter.

Recompute (PURE re-aggregation of stored per-task counts -- NO oracle runs) over the
remaining 15 tasks and compare to the full 22-task numbers:
 (a) July panel (results/frontier_n10/*): per-model compile-and-invariant AND
     all-checks-pass pass@1/pass@10.
 (b) Trained 7B models: base / SFT(3ep) / SFT-v2 / SFT-lite / RL-lite / SFT->RL from
     results/exp1a/*_s*.json (c_verified + c_taskvalid); RL-func from
     results/exp1b/rlfunc_sftlite_s*.json; RL-gated from
     results/exp_gated/rlgated_sftlite_s*.json. Seed mean +/- POPULATION SD.

Then check every RANKING the paper leans on, 15-task vs 22-task, and FLAG any rank
flip / sign change:
  R1  API model order (compile-and-invariant AND all-checks-pass pass@1)
  R2  SFT-v2 strongest all-checks-pass (task-valid) among trained
  R3  RL-gated highest compile-and-invariant (verified) among trained
  R4  RL-func > SFT-lite gain on all-checks-pass (task-valid) pass@1

Run: wsl bash toolchain/wsl_analysis.sh analysis/defect_mask_sensitivity.py
(No harness needed -- pure JSON aggregation -- but run under the harness for parity.)
"""
from __future__ import annotations
import glob, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "defect_mask_sensitivity.json")
FRONTIER = os.path.join(ROOT, "results", "frontier_n10")

EXCLUDED = {
    "E03_airlock_interlock", "M02_star_delta_starter", "M03_pedestrian_crossing",
    "M06_burner_purge_sequence", "M07_two_hand_control", "H03_batch_reactor_sequence",
    "H04_parking_garage_counter",
}

API_MODELS = [
    ("grok",   "grok_grok-3.json",                "grok-4.3 (grok-3 slug)"),
    ("claude", "anthropic_claude-sonnet-4-6.json", "claude-sonnet-4-6"),
    ("gemini", "gemini_gemini-2.5-flash.json",     "gemini-2.5-flash"),
    ("gpt-4o", "openai_gpt-4o.json",               "gpt-4o"),
]
# condition display -> (subdir, glob-prefix)
TRAINED = [
    ("base",     "exp1a", "base"),
    ("SFT",      "exp1a", "sft"),       # 3-epoch SFT
    ("SFT-v2",   "exp1a", "sftv2"),
    ("SFT-lite", "exp1a", "sftlite"),
    ("RL-lite",  "exp1a", "rllite"),
    ("SFT->RL",  "exp1a", "rl"),
    ("RL-func",  "exp1b", "rlfunc_sftlite"),
    ("RL-gated", "exp_gated", "rlgated_sftlite"),
]


def passk(n, c, k):
    if k > n:
        return 1.0 if c > 0 else 0.0
    if c <= 0:
        return 0.0
    if c >= n:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def agg_rows(rows, field, k):
    """Unbiased pass@k averaged over the given task rows."""
    if not rows:
        return 0.0
    return sum(passk(r["n"], r.get(field, 0), k) for r in rows) / len(rows)


def frontier_rows(fname):
    doc = json.load(open(os.path.join(FRONTIER, fname), encoding="utf-8"))
    out = []
    for r in doc["rows"]:
        out.append({"task_id": r["task_id"], "n": len(r["samples"]),
                    "c_verified": r["c_verified"], "c_taskvalid": r["c_taskvalid"]})
    return out


def seed_files(subdir, prefix):
    return sorted(glob.glob(os.path.join(ROOT, "results", subdir, f"{prefix}_s*.json")))


def load_seed_rows(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["rows"]


def subset(rows, keep_15):
    if keep_15:
        return [r for r in rows if r["task_id"] not in EXCLUDED]
    return rows


def mean_sd(xs):
    m = sum(xs) / len(xs)
    sd = (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5   # population SD (ddof=0)
    return m, sd


def rank(d, reverse=True):
    """Return keys ordered by value (desc)."""
    return [k for k, _ in sorted(d.items(), key=lambda kv: kv[1], reverse=reverse)]


def main():
    res = {
        "excluded_tasks": sorted(EXCLUDED),
        "n_tasks_full": 22, "n_tasks_retained": 15,
        "estimator": "unbiased Chen et al. pass@k; trained = mean +/- population SD over seeds",
        "api_panel": {"full22": {}, "retained15": {}},
        "trained": {"full22": {}, "retained15": {}},
        "rankings": {},
    }

    # ---- (a) API panel -------------------------------------------------------
    for key, fname, disp in API_MODELS:
        rows = frontier_rows(fname)
        for tag, keep in (("full22", False), ("retained15", True)):
            rs = subset(rows, keep)
            res["api_panel"][tag][key] = {
                "display": disp, "n_tasks": len(rs),
                "compile_and_invariant": {"pass@1": agg_rows(rs, "c_verified", 1),
                                          "pass@10": agg_rows(rs, "c_verified", 10)},
                "all_checks_pass": {"pass@1": agg_rows(rs, "c_taskvalid", 1),
                                    "pass@10": agg_rows(rs, "c_taskvalid", 10)},
            }

    # ---- (b) trained models --------------------------------------------------
    for disp, subdir, prefix in TRAINED:
        files = seed_files(subdir, prefix)
        seed_rows = [load_seed_rows(f) for f in files]
        for tag, keep in (("full22", False), ("retained15", True)):
            rec = {"n_seeds": len(files), "seed_files": [os.path.basename(f) for f in files]}
            for field, label in (("c_verified", "compile_and_invariant"),
                                 ("c_taskvalid", "all_checks_pass")):
                for k in (1, 10):
                    per_seed = [agg_rows(subset(sr, keep), field, k) for sr in seed_rows]
                    m, sd = mean_sd(per_seed)
                    rec.setdefault(label, {})[f"pass@{k}"] = {
                        "mean": m, "sd": sd, "per_seed": [round(x, 4) for x in per_seed]}
            res["trained"][tag][disp] = rec

    # ---- RANKINGS ------------------------------------------------------------
    def api_order(tag, metric):
        d = {k: res["api_panel"][tag][k][metric]["pass@1"] for k, _, _ in API_MODELS}
        return rank(d), d

    def trained_metric(tag, metric, k=1):
        return {disp: res["trained"][tag][disp][metric][f"pass@{k}"]["mean"] for disp, _, _ in TRAINED}

    R = res["rankings"]
    # R1 API order
    R["R1_api_order"] = {}
    for metric in ("compile_and_invariant", "all_checks_pass"):
        o22, d22 = api_order("full22", metric)
        o15, d15 = api_order("retained15", metric)
        R["R1_api_order"][metric] = {
            "full22_order": o22, "retained15_order": o15,
            "full22_vals": {k: round(v, 4) for k, v in d22.items()},
            "retained15_vals": {k: round(v, 4) for k, v in d15.items()},
            "rank_preserved": o22 == o15}
    # R2 SFT-v2 strongest task-valid among trained
    tv22 = trained_metric("full22", "all_checks_pass")
    tv15 = trained_metric("retained15", "all_checks_pass")
    R["R2_sftv2_top_taskvalid"] = {
        "full22_leader": rank(tv22)[0], "retained15_leader": rank(tv15)[0],
        "full22_vals": {k: round(v, 4) for k, v in tv22.items()},
        "retained15_vals": {k: round(v, 4) for k, v in tv15.items()},
        "holds_full22": rank(tv22)[0] == "SFT-v2",
        "holds_retained15": rank(tv15)[0] == "SFT-v2"}
    # R3 RL-gated highest verified (compile-and-invariant) among trained
    ci22 = trained_metric("full22", "compile_and_invariant")
    ci15 = trained_metric("retained15", "compile_and_invariant")
    R["R3_gated_top_verified"] = {
        "full22_leader": rank(ci22)[0], "retained15_leader": rank(ci15)[0],
        "full22_vals": {k: round(v, 4) for k, v in ci22.items()},
        "retained15_vals": {k: round(v, 4) for k, v in ci15.items()},
        "holds_full22": rank(ci22)[0] == "RL-gated",
        "holds_retained15": rank(ci15)[0] == "RL-gated"}
    # R4 RL-func vs SFT-lite gain on task-valid pass@1
    g22 = tv22["RL-func"] - tv22["SFT-lite"]
    g15 = tv15["RL-func"] - tv15["SFT-lite"]
    R["R4_rlfunc_gt_sftlite_taskvalid"] = {
        "full22_gain": round(g22, 4), "retained15_gain": round(g15, 4),
        "full22_rlfunc": round(tv22["RL-func"], 4), "full22_sftlite": round(tv22["SFT-lite"], 4),
        "retained15_rlfunc": round(tv15["RL-func"], 4), "retained15_sftlite": round(tv15["SFT-lite"], 4),
        "sign_preserved": (g22 > 0) == (g15 > 0)}

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    # ---------------------------- PRINT REPORT --------------------------------
    print("=" * 80)
    print("DELIVERABLE 2 -- 15-task (defect-masked) vs 22-task sensitivity")
    print("excluded:", ", ".join(sorted(EXCLUDED)))
    print("=" * 80)

    print("\n(a) API PANEL  [compile-and-invariant | all-checks-pass]  pass@1 (pass@10)")
    for key, fname, disp in API_MODELS:
        a22 = res["api_panel"]["full22"][key]; a15 = res["api_panel"]["retained15"][key]
        print(f"  {disp:26s}")
        print(f"    22-task  CI {a22['compile_and_invariant']['pass@1']:.3f} "
              f"({a22['compile_and_invariant']['pass@10']:.3f})   "
              f"ACP {a22['all_checks_pass']['pass@1']:.3f} ({a22['all_checks_pass']['pass@10']:.3f})")
        print(f"    15-task  CI {a15['compile_and_invariant']['pass@1']:.3f} "
              f"({a15['compile_and_invariant']['pass@10']:.3f})   "
              f"ACP {a15['all_checks_pass']['pass@1']:.3f} ({a15['all_checks_pass']['pass@10']:.3f})")

    print("\n(b) TRAINED MODELS  mean +/- pop-SD over seeds")
    print(f"  {'condition':10s} | {'CI p@1 (22)':>16s} {'CI p@1 (15)':>16s} | "
          f"{'ACP p@1 (22)':>16s} {'ACP p@1 (15)':>16s}")
    for disp, _, _ in TRAINED:
        t22 = res["trained"]["full22"][disp]; t15 = res["trained"]["retained15"][disp]
        ci22m = t22["compile_and_invariant"]["pass@1"]; ci15m = t15["compile_and_invariant"]["pass@1"]
        tv22m = t22["all_checks_pass"]["pass@1"];        tv15m = t15["all_checks_pass"]["pass@1"]
        print(f"  {disp:10s} | {ci22m['mean']:.3f}+/-{ci22m['sd']:.3f}   "
              f"{ci15m['mean']:.3f}+/-{ci15m['sd']:.3f}  | "
              f"{tv22m['mean']:.3f}+/-{tv22m['sd']:.3f}   {tv15m['mean']:.3f}+/-{tv15m['sd']:.3f}")

    print("\n---------------- RANKING VERDICTS (22 vs 15) ----------------")
    for metric in ("compile_and_invariant", "all_checks_pass"):
        r = R["R1_api_order"][metric]
        verdict = "HOLD" if r["rank_preserved"] else "*** FLIP ***"
        print(f"R1 API order [{metric}]: 22={' > '.join(r['full22_order'])} | "
              f"15={' > '.join(r['retained15_order'])}  -> {verdict}")
    r = R["R2_sftv2_top_taskvalid"]
    print(f"R2 SFT-v2 top task-valid: 22-leader={r['full22_leader']} 15-leader={r['retained15_leader']} "
          f"-> {'HOLD' if (r['holds_full22'] and r['holds_retained15']) else '*** CHECK ***'}")
    r = R["R3_gated_top_verified"]
    print(f"R3 RL-gated top verified: 22-leader={r['full22_leader']} 15-leader={r['retained15_leader']} "
          f"-> {'HOLD' if (r['holds_full22'] and r['holds_retained15']) else '*** CHECK ***'}")
    r = R["R4_rlfunc_gt_sftlite_taskvalid"]
    print(f"R4 RL-func>SFT-lite (task-valid p@1): 22-gain={r['full22_gain']:+.3f} "
          f"15-gain={r['retained15_gain']:+.3f} -> "
          f"{'HOLD' if r['sign_preserved'] else '*** SIGN FLIP ***'}")

    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
