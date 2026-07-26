"""ITEM 20 (round-16): attribute the T#1s delayed-Q verdict flips
(results/t1s_boundary_audit.json) to specific HEADLINE-TABLE CELLS, so the
integrator can quote per-table worst-case deltas.

The audit reports flips per DATASET only. Here we map each flipped (task_id, code)
unit back to the individual samples in each result file (per model for the July
API panels; per condition+seed for the training tables), reusing the audit's
cached std-vs-variant verdicts (no nuXmv re-run). We then bound the pass@1 /
pass@10 shift each table cell could see.

pass@1 over 22 tasks, n=10/task: one sample verdict flip moves that model's
pass@1 by exactly 1/220 = 0.004545. pass@10 (fraction of tasks with >=1 pass in
10) moves by 1/22 = 0.04545 only if the flip changes a task's any-pass status.

Run: python analysis/t1s_cell_attribution.py
"""
from __future__ import annotations
import glob, hashlib, json, os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = json.load(open(os.path.join(ROOT, "results", "t1s_boundary_audit.json"), encoding="utf-8"))

# changed units keyed by (task_id, sha1[:12]) -> verdicts
CU = {(u["task_id"], u["code_sha1"]): u for u in AUDIT["changed_units"]}


def sha12(code):
    return hashlib.sha1(code.encode()).hexdigest()[:12]


def clean(v):
    return v in ("pass", "fail")


def tv_flip(u, compile_ok):
    """Replicate t1s_boundary_audit.tally task-valid flip logic for one sample."""
    inv_s, inv_v = u["inv_std"], u["inv_var"]
    ss, sv = u["scen_std"], u["scen_var"]
    inv_comp = clean(inv_s) and clean(inv_v)
    scen_comp = ss in ("pass", "fail", "no_scenarios") and sv in ("pass", "fail", "no_scenarios")
    if not (inv_comp and scen_comp):
        return False
    tv_std = compile_ok and (inv_s == "pass") and (ss in ("pass", "no_scenarios"))
    tv_var = compile_ok and (inv_v == "pass") and (sv in ("pass", "no_scenarios"))
    return tv_std != tv_var


def inv_flip(u):
    return clean(u["inv_std"]) and clean(u["inv_var"]) and u["inv_std"] != u["inv_var"]


def analyze(files, cell_of):
    """cell_of(path) -> cell label. Returns per-cell dict."""
    cells = defaultdict(lambda: {"t1s_samples": 0, "tv_flips": 0, "inv_flips": 0,
                                 "tasks_with_tv_flip": set()})
    for f in sorted(files):
        if "output_activity" in f:
            continue
        d = json.load(open(f, encoding="utf-8"))
        if "rows" not in d:
            continue
        cell = cell_of(f)
        for row in d["rows"]:
            tid = row["task_id"]
            for s in row["samples"]:
                code = s.get("code") or ""
                if "t#1s" not in code.lower():
                    continue
                cells[cell]["t1s_samples"] += 1
                key = (tid, sha12(code))
                u = CU.get(key)
                if u is None:
                    continue
                if inv_flip(u):
                    cells[cell]["inv_flips"] += 1
                if tv_flip(u, bool(s.get("compile"))):
                    cells[cell]["tv_flips"] += 1
                    cells[cell]["tasks_with_tv_flip"].add(tid)
    # finalize
    out = {}
    for c, v in cells.items():
        out[c] = {"t1s_samples": v["t1s_samples"], "tv_flips": v["tv_flips"],
                  "inv_flips": v["inv_flips"],
                  "n_tasks_with_tv_flip": len(v["tasks_with_tv_flip"]),
                  "tasks_with_tv_flip": sorted(v["tasks_with_tv_flip"]),
                  "worst_pass1_delta": round(v["tv_flips"] / 220.0, 5),
                  "worst_pass10_delta_upper": round(len(v["tasks_with_tv_flip"]) / 22.0, 5)}
    return out


report = {}

# ---- July OPEN API panel (Table II / tab:taskvalid): per model, 220 samples ----
report["frontier_n10_open_per_model"] = analyze(
    glob.glob(os.path.join(ROOT, "results", "frontier_n10", "*.json")),
    lambda f: os.path.basename(f).replace(".json", ""))

# ---- July CONSTRAINED API panel (supplement): per model, 220 samples ----
report["frontier_n10_constrained_per_model"] = analyze(
    glob.glob(os.path.join(ROOT, "results", "frontier_n10_constrained", "*.json")),
    lambda f: os.path.basename(f).replace(".json", ""))

# ---- Training tables exp1a: per condition+seed ----
report["exp1a_per_cond_seed"] = analyze(
    glob.glob(os.path.join(ROOT, "results", "exp1a", "*_s*.json")),
    lambda f: os.path.basename(f).replace(".json", ""))

# ---- exp1b ----
report["exp1b_per_cond_seed"] = analyze(
    glob.glob(os.path.join(ROOT, "results", "exp1b", "*_s*.json")),
    lambda f: os.path.basename(f).replace(".json", ""))

# exp1a per-condition rollup (pool seeds): cell = 3- or 5-seed mean pass@1
cond_roll = defaultdict(lambda: {"tv_flips": 0, "t1s_samples": 0, "seeds": set()})
for cellseed, v in report["exp1a_per_cond_seed"].items():
    cond = cellseed.rsplit("_s", 1)[0]
    seed = cellseed.rsplit("_s", 1)[1]
    cond_roll[cond]["tv_flips"] += v["tv_flips"]
    cond_roll[cond]["t1s_samples"] += v["t1s_samples"]
    cond_roll[cond]["seeds"].add(seed)
exp1a_cond = {}
for cond, v in cond_roll.items():
    nseeds = len(v["seeds"])
    # cell = mean over seeds of pass@1; each flip moves one seed's pass@1 by 1/220,
    # so the mean by 1/(220*nseeds). Worst case all flips same direction:
    exp1a_cond[cond] = {"tv_flips_total": v["tv_flips"], "t1s_samples": v["t1s_samples"],
                        "nseeds": nseeds,
                        "worst_mean_pass1_delta": round(v["tv_flips"] / (220.0 * nseeds), 5)}
report["exp1a_condition_rollup"] = exp1a_cond

with open(os.path.join(ROOT, "results", "t1s_cell_attribution.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)

# ---- print ----
def show(title, d):
    print(f"\n== {title} ==")
    for cell, v in sorted(d.items()):
        print(f"  {cell:34s} T#1s={v['t1s_samples']:>3}  tv_flips={v['tv_flips']}  "
              f"inv_flips={v['inv_flips']}  tasks_flip={v['n_tasks_with_tv_flip']}  "
              f"worst d(pass@1)={v['worst_pass1_delta']:.5f}  "
              f"worst d(pass@10)<={v['worst_pass10_delta_upper']:.5f}"
              + (f"  {v['tasks_with_tv_flip']}" if v['tv_flips'] else ""))

show("Table II July OPEN panel (per model, 220 samples/model)", report["frontier_n10_open_per_model"])
show("July CONSTRAINED panel (per model, 220 samples/model)", report["frontier_n10_constrained_per_model"])
show("exp1a training (per condition+seed)", report["exp1a_per_cond_seed"])
show("exp1b (per condition+seed)", report["exp1b_per_cond_seed"])
print("\n== exp1a condition rollup (cell = seed-mean pass@1) ==")
for cond, v in sorted(exp1a_cond.items()):
    print(f"  {cond:14s} tv_flips_total={v['tv_flips_total']} over {v['nseeds']} seeds "
          f"({v['t1s_samples']} T#1s samples)  worst d(mean pass@1)={v['worst_mean_pass1_delta']:.5f}")
print("\nwrote results/t1s_cell_attribution.json")
