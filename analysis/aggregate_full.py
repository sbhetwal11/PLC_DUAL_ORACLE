"""Aggregate analysis.eval_full per-seed outputs into mean±std tables with paired
seed differences and task-by-seed hierarchical bootstrap CIs (DeepReview M16).

Reads results/<dir>/<stage>_s<seed>.json (as written by analysis.eval_full) and
reports, for each requested metric (verified / taskvalid) and k:
  - per-seed pass@k values + mean±std across seeds
  - paired seed differences between consecutive stages (e.g. RL - SFT per seed)
  - a hierarchical bootstrap 95% CI on pass@1 (resample tasks, then seeds)

    python -m analysis.aggregate_full --dir results/exp1a \
        --stages base,sft,rl,sftv2 --seeds 0,1,2 --metric taskvalid
"""
from __future__ import annotations

import argparse
import json
import os
import random
from statistics import mean, pstdev

from plcbench.generate.evaluate import pass_at_k


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _stage_files(dir_, stage, seeds):
    out = []
    for s in seeds:
        p = os.path.join(dir_, f"{stage}_s{s}.json")
        if os.path.exists(p):
            out.append((s, _load(p)))
    return out


def _ms(xs):
    return {"mean": round(mean(xs), 4), "std": round(pstdev(xs), 4),
            "n": len(xs), "vals": [round(x, 4) for x in xs]} if xs else None


def hierarchical_bootstrap_pass1(files, field, k=1, B=2000, seed=12345):
    """CI on pass@k: for each bootstrap draw, resample tasks (with replacement) and
    seeds (with replacement), average pass@k of the resampled (task,seed) cells."""
    rng = random.Random(seed)
    # per-seed list of task rows
    seed_rows = [d["rows"] for _, d in files]
    if not seed_rows:
        return None
    T = len(seed_rows[0])
    S = len(seed_rows)
    means = []
    for _ in range(B):
        task_idx = [rng.randrange(T) for _ in range(T)]
        acc = 0.0
        for ti in task_idx:
            si = rng.randrange(S)
            r = seed_rows[si][ti]
            acc += pass_at_k(r["n"], r[field], k) if r["n"] > 0 else 0.0
        means.append(acc / T)
    means.sort()
    lo = means[int(0.025 * B)]
    hi = means[int(0.975 * B)]
    return {"mean": round(mean(means), 4), "ci95": [round(lo, 4), round(hi, 4)]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--stages", required=True, help="comma-separated stage prefixes")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--metric", default="taskvalid", choices=["verified", "taskvalid", "both"])
    ap.add_argument("--ks", default="1,3,5,10")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    stages = [s for s in args.stages.split(",") if s]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    ks = [int(k) for k in args.ks.split(",") if k.strip()]
    metrics = ["verified", "taskvalid"] if args.metric == "both" else [args.metric]
    field_of = {"verified": "c_verified", "taskvalid": "c_taskvalid"}

    result = {"dir": args.dir, "seeds": seeds, "stages": {}}
    for stage in stages:
        files = _stage_files(args.dir, stage, seeds)
        if not files:
            continue
        entry = {"seeds_present": [s for s, _ in files]}
        for metric in metrics:
            key = lambda k: f"{metric}_pass@{k}"
            perseed = {k: [d["summary"][key(k)] for _, d in files] for k in ks}
            entry[metric] = {f"pass@{k}": _ms(perseed[k]) for k in ks}
            entry[metric]["boot_pass@1"] = hierarchical_bootstrap_pass1(
                files, field_of[metric], k=1)
        result["stages"][stage] = entry

    # paired seed diffs between consecutive stages
    result["paired_diffs"] = {}
    for metric in metrics:
        for a, b in zip(stages, stages[1:]):
            fa = dict(_stage_files(args.dir, a, seeds))
            fb = dict(_stage_files(args.dir, b, seeds))
            common = sorted(set(fa) & set(fb))
            if not common:
                continue
            diffs = [fb[s]["summary"][f"{metric}_pass@1"] -
                     fa[s]["summary"][f"{metric}_pass@1"] for s in common]
            result["paired_diffs"][f"{metric}:{b}-{a}"] = {
                "per_seed": [round(x, 4) for x in diffs], "mean": round(mean(diffs), 4),
                "std": round(pstdev(diffs), 4), "seeds": common}

    # print
    for stage, e in result["stages"].items():
        line = [f"{stage:16s}"]
        for metric in metrics:
            m1 = e[metric]["pass@1"]; m10 = e[metric].get("pass@10")
            b = e[metric]["boot_pass@1"]
            line.append(f"{metric}: p1={m1['mean']:.3f}±{m1['std']:.3f} "
                        f"[{b['ci95'][0]:.3f},{b['ci95'][1]:.3f}]"
                        f"{' p10=%.3f' % m10['mean'] if m10 else ''}")
        print("  ".join(line))
    if result["paired_diffs"]:
        print("\npaired diffs (pass@1):")
        for k, v in result["paired_diffs"].items():
            print(f"  {k:28s} {v['mean']:+.4f} ± {v['std']:.4f}  per-seed {v['per_seed']}")

    out = args.out or os.path.join(args.dir, f"summary_{args.metric}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
