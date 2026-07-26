"""C1: matched-seed paired comparison of task-valid pass@1.

SFT-lite (results/exp1a/sftlite_s{seed}.json) vs functional-reward RL
(results/exp1b/rlfunc_sftlite_s{seed}.json), warm-started from SFT-lite
seeds 0,1,2. Unbiased pass@k estimator, k=1, n=10, averaged over the 22 tasks.
Pure JSON; Windows python OK.
"""
from __future__ import annotations
import json, math, os, statistics

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pass_at_k(n, c, k):
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def taskvalid_pass_at_1(path):
    d = json.load(open(path, encoding="utf-8"))
    rows = d["rows"]
    n = d["n"]
    vals = [pass_at_k(n, r["c_taskvalid"], 1) for r in rows]
    return sum(vals) / len(vals), len(rows), n


def sft_path(seed):
    return os.path.join(REPO, "results", "exp1a", f"sftlite_s{seed}.json")


def rl_path(seed):
    return os.path.join(REPO, "results", "exp1b", f"rlfunc_sftlite_s{seed}.json")


def main():
    paired_seeds = [0, 1, 2]
    all_sft_seeds = [0, 1, 2, 3, 4]

    per_seed = []
    diffs = []
    for s in paired_seeds:
        sft_pk, sft_ntasks, sft_n = taskvalid_pass_at_1(sft_path(s))
        rl_pk, rl_ntasks, rl_n = taskvalid_pass_at_1(rl_path(s))
        d = rl_pk - sft_pk
        diffs.append(d)
        per_seed.append({
            "seed": s,
            "sftlite_pass1": sft_pk,
            "rl_pass1": rl_pk,
            "diff_rl_minus_sft": d,
            "sft_ntasks": sft_ntasks, "sft_n": sft_n,
            "rl_ntasks": rl_ntasks, "rl_n": rl_n,
        })

    sft3 = [taskvalid_pass_at_1(sft_path(s))[0] for s in paired_seeds]
    sft5 = [taskvalid_pass_at_1(sft_path(s))[0] for s in all_sft_seeds]
    rl3 = [taskvalid_pass_at_1(rl_path(s))[0] for s in paired_seeds]

    result = {
        "metric": "taskvalid pass@1, unbiased estimator, k=1, n=10, mean over 22 tasks",
        "per_seed": per_seed,
        "paired_diffs": diffs,
        "paired_diff_mean": statistics.mean(diffs),
        "paired_diff_sd": statistics.stdev(diffs),
        "sftlite_3seed_mean": statistics.mean(sft3),
        "sftlite_3seed_sd": statistics.stdev(sft3),
        "sftlite_5seed_mean": statistics.mean(sft5),
        "sftlite_5seed_sd": statistics.stdev(sft5),
        "rl_3seed_mean": statistics.mean(rl3),
        "rl_3seed_sd": statistics.stdev(rl3),
    }

    print("=== C1: matched-seed paired comparison (task-valid pass@1) ===")
    print(f"{'seed':>4} {'SFT-lite':>10} {'RL-func':>10} {'diff':>10}")
    for p in per_seed:
        print(f"{p['seed']:>4} {p['sftlite_pass1']:>10.4f} {p['rl_pass1']:>10.4f} "
              f"{p['diff_rl_minus_sft']:>+10.4f}")
    print("-" * 38)
    print(f"paired diff  mean={result['paired_diff_mean']:+.4f}  "
          f"sd={result['paired_diff_sd']:.4f}")
    print(f"SFT-lite 3-seed  mean={result['sftlite_3seed_mean']:.4f}  "
          f"sd={result['sftlite_3seed_sd']:.4f}")
    print(f"SFT-lite 5-seed  mean={result['sftlite_5seed_mean']:.4f}  "
          f"sd={result['sftlite_5seed_sd']:.4f}  (reference)")
    print(f"RL 3-seed        mean={result['rl_3seed_mean']:.4f}  "
          f"sd={result['rl_3seed_sd']:.4f}  (sanity ~0.282)")

    outdir = os.path.join(REPO, "results")
    outpath = os.path.join(outdir, "matched_seeds.json")
    json.dump(result, open(outpath, "w", encoding="utf-8"), indent=2)
    print(f"\nsaved {outpath}")


if __name__ == "__main__":
    main()
