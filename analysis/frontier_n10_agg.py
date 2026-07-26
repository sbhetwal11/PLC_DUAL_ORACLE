"""Aggregate the July-2026 n=10 API panel (results/frontier_n10/) into pass@k
per dimension (compile / invariant / scenario / task-valid), unbiased estimator."""
from __future__ import annotations
import glob, json, math, os, sys


def pass_at_k(n, c, k):
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def agg(path):
    d = json.load(open(path, encoding="utf-8"))
    rows = d["rows"]
    n = d["n"]
    out = {"model": d["model_spec"], "tasks": len(rows),
           "window": d.get("access_window"), "n": n}
    for dim, key in [("compile", "c_compile"), ("invariant", "c_verified"),
                     ("scenario", "c_scenario"), ("taskvalid", "c_taskvalid")]:
        for k in (1, 10):
            v = sum(pass_at_k(n, r[key], k) for r in rows) / len(rows)
            out[f"{dim}@{k}"] = round(v, 3)
    out["total_errors"] = sum(r["n_errors"] for r in rows)
    return out


def main():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "results", "frontier_n10")
    for p in sorted(glob.glob(os.path.join(base, "*.json"))):
        a = agg(p)
        print(f"{a['model']:32s} tasks={a['tasks']:2d} window={a['window']} err={a['total_errors']}")
        print(f"  compile   @1 {a['compile@1']:.3f}  @10 {a['compile@10']:.3f}")
        print(f"  invariant @1 {a['invariant@1']:.3f}  @10 {a['invariant@10']:.3f}")
        print(f"  scenario  @1 {a['scenario@1']:.3f}  @10 {a['scenario@10']:.3f}")
        print(f"  TASKVALID @1 {a['taskvalid@1']:.3f}  @10 {a['taskvalid@10']:.3f}")


if __name__ == "__main__":
    main()
