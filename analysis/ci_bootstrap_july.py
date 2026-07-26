"""Round-12 item 11: primary uncertainty analysis on the July-2026 compile-and-invariant
panel (results/frontier_n10/). Paired task bootstrap for all six pairwise
compile-and-invariant pass@1 differences, per-model CIs (pass@1 and pass@10), and a
hierarchical variant resampling completions within tasks. 20,000 resamples,
seed 0. Also emits the per-task compile-and-invariant count matrix for the supplement.
Windows-safe (pure Python), run:  python analysis/ci_bootstrap_july.py
"""
from __future__ import annotations
import glob, json, math, os, random

B = 20000
SEED = 0
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "results", "frontier_n10")

def pass_at_k(n, c, k):
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)

def load():
    models = {}
    for p in sorted(glob.glob(os.path.join(BASE, "*.json"))):
        d = json.load(open(p, encoding="utf-8"))
        name = d["model_spec"].split(":", 1)[1]
        rows = sorted(d["rows"], key=lambda r: r["task_id"])
        models[name] = {"n": d["n"],
                        "tasks": [r["task_id"] for r in rows],
                        "c": [r["c_verified"] for r in rows]}
    tasks = None
    for m in models.values():
        assert tasks is None or m["tasks"] == tasks
        tasks = m["tasks"]
    return models, tasks

def ci(vals, lo=2.5, hi=97.5):
    s = sorted(vals)
    return (s[int(len(s) * lo / 100)], s[min(int(len(s) * hi / 100), len(s) - 1)])

def main():
    models, tasks = load()
    T = len(tasks)
    names = sorted(models, key=lambda m: -sum(models[m]["c"]))
    n = 10
    rng = random.Random(SEED)
    print(f"July-2026 compile-and-invariant panel bootstrap: B={B}, seed={SEED}, tasks={T}, n={n}\n")

    p1 = {m: [pass_at_k(n, c, 1) for c in models[m]["c"]] for m in names}
    p10 = {m: [pass_at_k(n, c, 10) for c in models[m]["c"]] for m in names}

    # --- per-model CIs + pairwise paired differences (task bootstrap) ----------
    idx_draws = [[rng.randrange(T) for _ in range(T)] for _ in range(B)]
    print("## per-model task-bootstrap 95% CIs")
    for m in names:
        b1 = [sum(p1[m][i] for i in idx) / T for idx in idx_draws]
        b10 = [sum(p10[m][i] for i in idx) / T for idx in idx_draws]
        print(f"  {m:22s} TV@1 {sum(p1[m])/T:.3f} CI [{ci(b1)[0]:.3f},{ci(b1)[1]:.3f}]"
              f"   TV@10 {sum(p10[m])/T:.3f} CI [{ci(b10)[0]:.3f},{ci(b10)[1]:.3f}]")

    print("\n## paired task-bootstrap differences, TV@1 (A-B), 95% CI "
          "(6 unadjusted contrasts: exploratory)")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            d = [p1[a][t] - p1[b][t] for t in range(T)]
            bd = [sum(d[t] for t in idx) / T for idx in idx_draws]
            lo, hi = ci(bd)
            excl = "excludes 0" if lo > 0 or hi < 0 else "includes 0"
            print(f"  {a} - {b}: {sum(d)/T:+.3f} CI [{lo:+.3f},{hi:+.3f}]  ({excl})")

    # --- hierarchical: resample tasks, then completions within task ------------
    print("\n## hierarchical bootstrap (tasks, then completions), TV@1")
    for m in names:
        cs = models[m]["c"]
        bs = []
        for _ in range(B // 4):        # 5000 draws is plenty for a check
            tot = 0.0
            for i in [rng.randrange(T) for _ in range(T)]:
                c = sum(1 for _ in range(n) if rng.random() < cs[i] / n)
                tot += pass_at_k(n, c, 1)
            bs.append(tot / T)
        lo, hi = ci(bs)
        print(f"  {m:22s} CI [{lo:.3f},{hi:.3f}]")

    # --- per-task count matrix (supplement) ------------------------------------
    print("\n## per-task compile-and-invariant counts (out of n=10)")
    hdr = "task    " + "  ".join(f"{m[:9]:>9s}" for m in names)
    print(hdr)
    for t in range(T):
        tid = tasks[t].split("_")[0]
        print(f"{tid:8s}" + "  ".join(f"{models[m]['c'][t]:9d}" for m in names))

if __name__ == "__main__":
    main()
