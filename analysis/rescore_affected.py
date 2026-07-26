"""Re-score, under the FIXED translator pre-seed, every evaluated sample that
reads a TON's Q before that timer's call (the only construct whose translation
changed). Reports verdict flips against the stored flags; does not modify the
stored result files (flips are reported for the paper and the artifact).

Run: wsl bash toolchain/wsl_analysis.sh analysis/rescore_affected.py
"""
from __future__ import annotations
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness
from analysis.qbeforecall_scan import reads_q_before_call

by_id = {lt.task.id: lt for lt in load_all()}


def rescore(code, tid):
    lt = by_id.get(tid)
    if lt is None:
        lt = next((v for k, v in by_id.items()
                   if k.startswith(tid) or tid.startswith(k)), None)
    if lt is None or not code.strip():
        return None
    ev = harness.evaluate(lt.task, code)
    c = ev.compiles is True
    i = ev.verified is True
    s = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
    return {"compile": c, "invariant": i, "scenario": s, "taskvalid": c and i and s}


def scan(pattern, label):
    checked = flips = 0
    details = []
    for f in sorted(glob.glob(pattern)):
        d = json.load(open(f, encoding="utf-8"))
        for row in d["rows"]:
            tid = row["task_id"]
            for si, s in enumerate(row["samples"]):
                code = (s.get("code") or "").strip()
                if not code or not reads_q_before_call(code):
                    continue
                new = rescore(code, tid)
                if new is None:
                    continue
                checked += 1
                for k in ("invariant", "taskvalid"):
                    old = bool(s.get(k))
                    if old != new[k]:
                        flips += 1
                        details.append((os.path.basename(f), tid, si, k, old, new[k]))
    print(f"{label}: re-scored {checked} affected samples; verdict flips: {flips}")
    for x in details:
        print("   FLIP:", x)
    return details


def main():
    all_flips = []
    all_flips += scan("results/exp1a/*_s*.json", "exp1a")
    all_flips += scan("results/exp1b/*_s*.json", "exp1b")
    all_flips += scan("results/frontier_n10/*.json", "july_panel")
    with open("results/difftest/qbeforecall_rescore.json", "w", encoding="utf-8") as f:
        json.dump({"flips": all_flips}, f, indent=1)
    print("total flips:", len(all_flips))


if __name__ == "__main__":
    main()
