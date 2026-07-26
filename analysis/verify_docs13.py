"""Independently recompute every headline number from the raw per-seed result files
and compare to what docs/13 claims. Trust nothing; recompute from c_taskvalid counts
with the unbiased pass@k estimator (Chen et al.) and average over seeds.
"""
import json, glob, os, re, math
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def passk_from_counts(rows, field, k):
    """Unbiased pass@k over tasks from per-task counts of 'field' out of n."""
    vals = []
    for r in rows:
        n = r["n"]; c = r.get(field, 0)
        if k > n:
            vals.append(1.0 if c > 0 else 0.0); continue
        # 1 - C(n-c, k)/C(n, k)
        if c == 0:
            vals.append(0.0)
        elif c >= n:
            vals.append(1.0)
        else:
            vals.append(1.0 - math.comb(n - c, k) / math.comb(n, k))
    return sum(vals) / len(vals) if vals else 0.0


def load_group(exp, cond):
    files = sorted(glob.glob(os.path.join(ROOT, "results", exp, f"{cond}_s*.json")))
    return files


def agg(exp, cond, field="taskvalid", ks=(1, 10)):
    files = load_group(exp, cond)
    if not files:
        return None
    per_seed = {k: [] for k in ks}
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        rows = d["rows"]
        for k in ks:
            per_seed[k].append(passk_from_counts(rows, f"c_{field}", k))
    out = {}
    for k in ks:
        xs = per_seed[k]
        m = sum(xs) / len(xs)
        sd = (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5
        out[k] = (m, sd, len(xs))
    return out


def show(title, exp, conds, field="taskvalid"):
    print(f"\n## {title}  (recomputed from raw c_{field} counts)")
    for cond in conds:
        a = agg(exp, cond, field)
        if a is None:
            print(f"  {cond:24s} MISSING"); continue
        p1 = a[1]; p10 = a[10]
        print(f"  {cond:24s} p@1 {p1[0]:.3f}±{p1[1]:.3f} (n={p1[2]})   p@10 {p10[0]:.3f}")


# Exp1a - existing trained models, task-valid
show("Exp1a task-valid (existing models)", "exp1a",
     ["base", "sft", "rl", "sftv2", "sftlite", "rllite"], "taskvalid")
show("Exp1a verified (cross-check vs prior macros)", "exp1a",
     ["base", "sft", "rl", "sftlite", "rllite"], "verified")
# Exp1b - functional reward
show("Exp1b functional-reward RL", "exp1b", ["rlfunc_sftlite"], "taskvalid")
show("Exp1b functional-reward RL (verified)", "exp1b", ["rlfunc_sftlite"], "verified")
# Exp2 - filtering ablation
show("Exp2 filtering ablation", "exp2",
     ["abl_all", "abl_matiec_only", "abl_property_only", "abl_dual", "abl_random_sizematched"], "taskvalid")
# Exp5 - repair controls
show("Exp5 repair controls", "exp5",
     ["rep_base", "rep_generic_sft", "rep_nocex", "rep_erroronly", "rep_proponly", "rep_shuffle", "rep_full"], "taskvalid")
# Exp6 - fixed-frontier RL
show("Exp6 fixed-frontier RL", "exp6", ["rlfunc_base", "rlfunc_sft"], "taskvalid")

# Exp2 composition (reject rates)
for cf in ["composition", "composition_model"]:
    p = os.path.join(ROOT, "results", "exp2", f"{cf}.json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        print(f"\n## Exp2 {cf}: {json.dumps(d)[:400]}")
