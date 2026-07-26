"""Aggregate per-seed pass@k JSONs into mean +/- std tables.

Reads results/<dir>/<stage>_s<seed>.json for stage in {base,sft,rl} (override with
--stages) and seeds (default 0 1 2), prints overall and by-tier pass@k as mean+/-std,
and writes a machine-readable <dir>/summary.json.

    python -m finetune.aggregate_seeds --dir results/seeds --seeds 0 1 2
"""
from __future__ import annotations

import argparse
import json
import os
from statistics import mean, pstdev


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _collect(dir_, stage, seeds, ks):
    overall = {k: [] for k in ks}
    tiers = {}
    present = []
    for s in seeds:
        p = os.path.join(dir_, f"{stage}_s{s}.json")
        if not os.path.exists(p):
            continue
        present.append(s)
        d = _load(p)
        for k in ks:
            overall[k].append(d["summary"][k])
        for t, tk in d["by_tier"].items():
            tiers.setdefault(t, {k: [] for k in ks})
            for k in ks:
                tiers[t][k].append(tk[k])
    return overall, tiers, present


def _ms(xs):
    if not xs:
        return None
    return {"mean": round(mean(xs), 4), "std": round(pstdev(xs), 4), "n": len(xs), "vals": xs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/seeds")
    ap.add_argument("--stages", default="base,sft,rl")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--ks", default="pass@1,pass@3,pass@5,pass@10")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    stages = [s for s in args.stages.split(",") if s]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    ks = [k for k in args.ks.split(",") if k]

    summary = {"dir": args.dir, "seeds": seeds, "stages": {}}
    print(f"=== OVERALL pass@k mean +/- std (seeds {seeds}) ===")
    hdr = "stage   " + "  ".join(f"{k:>14}" for k in ks)
    print(hdr)
    for stage in stages:
        overall, tiers, present = _collect(args.dir, stage, seeds, ks)
        summary["stages"][stage] = {
            "seeds_present": present,
            "overall": {k: _ms(overall[k]) for k in ks},
            "by_tier": {t: {k: _ms(tiers[t][k]) for k in ks} for t in tiers}}
        cells = []
        for k in ks:
            ms = _ms(overall[k])
            cells.append(f"{ms['mean']:.3f}±{ms['std']:.3f}" if ms else f"{'--':>11}")
        print(f"{stage:7} " + "  ".join(f"{c:>14}" for c in cells))

    print("\n=== BY TIER pass@1 / pass@10 mean±std ===")
    for stage in stages:
        st = summary["stages"][stage]["by_tier"]
        parts = []
        for t in ("easy", "medium", "hard"):
            if t in st:
                p1, p10 = st[t].get("pass@1"), st[t].get("pass@10")
                if p1 and p10:
                    parts.append(f"{t} {p1['mean']:.3f}±{p1['std']:.3f}/"
                                 f"{p10['mean']:.3f}±{p10['std']:.3f}")
        print(f"{stage:7} " + "   ".join(parts))

    out = args.out or os.path.join(args.dir, "summary.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
