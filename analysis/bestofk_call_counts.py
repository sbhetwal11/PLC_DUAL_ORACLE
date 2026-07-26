"""DELIVERABLE 3 (final-revision round): BEST-OF-K EMPIRICAL ORACLE-CALL COUNTS.

From results/exp7/{base,sft}_infer_s{0,1,2}.json extract best_of_k.mean_oracle_calls
per seed and condition; report the 3-seed means and the empirical cost ratio for the
sentence "RL single call vs SFT best-of-ten" = 1 / mean_sft_calls.

Run: wsl bash toolchain/wsl_analysis.sh analysis/bestofk_call_counts.py
(Pure JSON read -- no oracle runs.)
"""
from __future__ import annotations
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "bestofk_call_counts.json")
EXP7 = os.path.join(ROOT, "results", "exp7")
SEEDS = [0, 1, 2]
K = 10  # best-of-k cap (repair_rounds/k in the files)


def mean(xs):
    return sum(xs) / len(xs)


def sd_pop(xs):
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def load(cond):
    rows = {}
    for s in SEEDS:
        d = json.load(open(os.path.join(EXP7, f"{cond}_infer_s{s}.json"), encoding="utf-8"))
        bok = d["best_of_k"]
        rows[s] = {"mean_oracle_calls": bok["mean_oracle_calls"],
                   "total_oracle_calls": bok["total_oracle_calls"],
                   "success_rate": bok["success_rate"],
                   "tasks": bok["tasks"], "k": d.get("k")}
    return rows


def main():
    res = {"source": "results/exp7/{base,sft}_infer_s{0,1,2}.json  (best_of_k block)",
           "k_cap": K, "per_condition": {}}
    for cond in ("base", "sft"):
        rows = load(cond)
        calls = [rows[s]["mean_oracle_calls"] for s in SEEDS]
        res["per_condition"][cond] = {
            "per_seed_mean_oracle_calls": {str(s): rows[s]["mean_oracle_calls"] for s in SEEDS},
            "per_seed_success_rate": {str(s): rows[s]["success_rate"] for s in SEEDS},
            "three_seed_mean_oracle_calls": mean(calls),
            "three_seed_sd_oracle_calls": sd_pop(calls),
        }
    base_calls = res["per_condition"]["base"]["three_seed_mean_oracle_calls"]
    sft_calls = res["per_condition"]["sft"]["three_seed_mean_oracle_calls"]
    res["cost_ratio_rl_single_vs_sft_bestof10"] = {
        "formula": "1 / mean_sft_best_of_k_oracle_calls",
        "value": 1.0 / sft_calls,
        "mean_sft_calls": sft_calls, "mean_base_calls": base_calls,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    print("=" * 70)
    print("DELIVERABLE 3 -- best-of-k empirical oracle-call counts")
    print("=" * 70)
    for cond in ("base", "sft"):
        c = res["per_condition"][cond]
        ps = c["per_seed_mean_oracle_calls"]
        print(f"\n{cond.upper():5s} mean_oracle_calls per seed: "
              f"s0={ps['0']}  s1={ps['1']}  s2={ps['2']}")
        print(f"      3-seed mean = {c['three_seed_mean_oracle_calls']:.4f} "
              f"+/- {c['three_seed_sd_oracle_calls']:.4f} (pop SD)")
    r = res["cost_ratio_rl_single_vs_sft_bestof10"]
    print(f"\nEmpirical cost ratio (RL single call vs SFT best-of-{K}):")
    print(f"  1 / mean_sft_calls = 1 / {sft_calls:.4f} = {r['value']:.4f}")
    print(f"  (base best-of-{K} mean calls = {base_calls:.4f})")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
