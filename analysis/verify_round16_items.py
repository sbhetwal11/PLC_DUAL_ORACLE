"""Round-16 counts-based verification for items 10, 11, 13, 17.
Pure recompute from stored per-task counts (no nuXmv needed); unbiased pass@k
estimator identical to analysis/verify_docs13.py. Saves results/round16_items.json.

Run: python analysis/verify_round16_items.py   (or under the WSL harness)
"""
from __future__ import annotations
import glob, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def passk_from_counts(rows, field, k):
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


def per_seed_passk(exp, cond, field, k):
    files = sorted(glob.glob(os.path.join(ROOT, "results", exp, f"{cond}_s*.json")))
    out = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        out.append((os.path.basename(f), passk_from_counts(d["rows"], field, k)))
    return out


def mean_std(vals):
    m = sum(vals) / len(vals)
    sd = (sum((x - m) ** 2 for x in vals) / len(vals)) ** 0.5
    return m, sd


res = {}

# ---------------- ITEM 17: exact +/-0.000 pass@10 ----------------
print("=== ITEM 17: task-valid pass@10 per-seed exactness ===")
item17 = {}
for label, exp, cond in [("SFT->RL (exp1a rl)", "exp1a", "rl"),
                         ("RL-func (exp1b rlfunc_sftlite)", "exp1b", "rlfunc_sftlite")]:
    ps = per_seed_passk(exp, cond, "c_taskvalid", 10)
    vals = [v for _, v in ps]
    m, sd = mean_std(vals)
    item17[label] = {"per_seed": {f: round(v, 6) for f, v in ps},
                     "mean": round(m, 6), "std": round(sd, 6)}
    print(f"  {label}: pass@10 per seed = {[round(v,6) for v in vals]}  mean {m:.6f} std {sd:.6f}")
res["item17"] = item17

# ---------------- ITEM 13: best-of-k provenance (exp7 fresh draws) ----------------
print("\n=== ITEM 13: best-of-ten (exp7 inference baselines, FRESH draws k=10) ===")
item13 = {}
for cond in ["base", "sft"]:
    files = sorted(glob.glob(os.path.join(ROOT, "results", "exp7", f"{cond}_infer_s*.json")))
    per = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        per.append((os.path.basename(f), d["best_of_k"]["success_rate"],
                    d["best_of_k"]["mean_oracle_calls"], d["repair"]["success_rate"]))
    vals = [v for _, v, _, _ in per]
    m, sd = mean_std(vals)
    item13[cond] = {"per_seed_best_of_10": {f: v for f, v, _, _ in per},
                    "mean_best_of_10": round(m, 4), "std": round(sd, 4),
                    "mean_oracle_calls": [c for _, _, c, _ in per]}
    print(f"  {cond} best-of-10: {vals}  mean {m:.4f} std {sd:.4f}  (calls {[c for _,_,c,_ in per]})")
res["item13"] = item13

# ---------------- ITEM 10: monotonicity triple (task-valid pass@1) ----------------
print("\n=== ITEM 10: monotonicity triple, task-valid pass@1 (fixed 39-prompt RL) ===")
item10 = {}
for label, exp, cond in [("RL-from-base (exp6 rlfunc_base)", "exp6", "rlfunc_base"),
                         ("RL-from-collapsed-3epoch-SFT (exp6 rlfunc_sft)", "exp6", "rlfunc_sft"),
                         ("RL-from-SFT-lite (exp1b rlfunc_sftlite)", "exp1b", "rlfunc_sftlite")]:
    ps = per_seed_passk(exp, cond, "c_taskvalid", 1)
    vals = [v for _, v in ps]
    m, sd = mean_std(vals)
    item10[label] = {"per_seed": {f: round(v, 4) for f, v in ps},
                     "mean_pass1": round(m, 4), "std": round(sd, 4)}
    print(f"  {label}: pass@1 per seed = {[round(v,4) for v in vals]}  mean {m:.4f} std {sd:.4f}")
res["item10"] = item10

# ---------------- ITEM 11: 0.311 (run B, exp1a) vs 0.314 (run A, seeds) ----------------
print("\n=== ITEM 11: SFT compile-and-invariant pass@1, run B (exp1a) vs run A (seeds) ===")
# run B: exp1a sft, field c_verified (compile-and-invariant)
psB = per_seed_passk("exp1a", "sft", "c_verified", 1)
valsB = [v for _, v in psB]; mB, sdB = mean_std(valsB)
# run A: results/seeds/summary.json stage sft overall pass@1
summ = json.load(open(os.path.join(ROOT, "results", "seeds", "summary.json"), encoding="utf-8"))
runA = summ["stages"]["sft"]["overall"]["pass@1"]
item11 = {"run_B_exp1a": {"per_seed": {f: round(v, 4) for f, v in psB},
                           "mean": round(mB, 4), "std": round(sdB, 4)},
          "run_A_seeds_summary": {"mean": runA["mean"], "std": runA["std"], "vals": runA["vals"]}}
print(f"  run B (exp1a sft, c_verified) pass@1 per seed = {[round(v,4) for v in valsB]}  mean {mB:.4f} std {sdB:.4f}")
print(f"  run A (results/seeds/summary.json sft) pass@1  = {runA['vals']}  mean {runA['mean']} std {runA['std']}")
res["item11"] = item11

with open(os.path.join(ROOT, "results", "round16_items.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, indent=1)
print("\nwrote results/round16_items.json")
