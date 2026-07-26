# -*- coding: utf-8 -*-
"""Recompute the paper's matched-seed / paired-diff SDs under the paper-wide
POPULATION-SD (ddof=0) convention, from raw per-seed summary JSONs.

Motivation: every stored summary JSON and every training-table +/- follows
population SD (ddof=0). A handful of matched-seed / paired-diff SDs in the
S.XVIII paragraphs (and docs/15) leaked ddof=1. This script recomputes each
affected quantity with ddof=0, and also prints the ddof=1 value to confirm it
reproduces the current (wrong) paper number, so each old->new mapping is auditable.

Run:  wsl bash toolchain/wsl_analysis.sh analysis/sd_convention_fix.py
Writes: results/sd_convention_fix.json
"""
from __future__ import annotations
import json, os, statistics as st

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    with open(os.path.join(REPO, path), encoding="utf-8") as f:
        return json.load(f)


def summ(stage_dir, stage, seeds, key):
    """Return list of summary[key] over the given seeds."""
    out = []
    for s in seeds:
        d = load(f"{stage_dir}/{stage}_s{s}.json")
        out.append(d["summary"][key])
    return out


def pstdev(xs):
    return st.pstdev(xs) if len(xs) > 1 else 0.0


def sstdev(xs):
    return st.stdev(xs) if len(xs) > 1 else 0.0


def block(label, xs, note=""):
    m = sum(xs) / len(xs)
    return {
        "label": label,
        "values": [round(x, 4) for x in xs],
        "mean": round(m, 4),
        "sd_pop_ddof0": round(pstdev(xs), 4),
        "sd_samp_ddof1": round(sstdev(xs), 4),
        "note": note,
    }


res = {}

# ---- (a) SFT-lite 5-seed task-valid pass@1 SD (expect ddof0 == table's 0.028) ----
sftlite5 = summ("results/exp1a", "sftlite", [0, 1, 2, 3, 4], "taskvalid_pass@1")
res["a_sftlite5_taskvalid_p1"] = block(
    "SFT-lite 5-seed task-valid pass@1", sftlite5,
    "table \\tvfiveSftliteS=0.028 ; paragraph currently 0.179+/-0.032 (ddof1)")

# ---- (b) SFT-lite 3-seed matched baseline task-valid pass@1 SD (currently 0.174+/-0.044) ----
sftlite3 = summ("results/exp1a", "sftlite", [0, 1, 2], "taskvalid_pass@1")
res["b_sftlite3_taskvalid_p1"] = block(
    "SFT-lite 3-seed (matched) task-valid pass@1", sftlite3,
    "paragraph currently 0.174+/-0.044 (ddof1)")

# ---- (c) SFT-lite -> RL-func paired diffs (task-valid pass@1), currently SD 0.046 ----
rlfunc3 = summ("results/exp1b", "rlfunc_sftlite", [0, 1, 2], "taskvalid_pass@1")
diffs_c = [r - s for r, s in zip(rlfunc3, sftlite3)]
res["c_paired_rlfunc_minus_sftlite_taskvalid_p1"] = block(
    "paired diff RL-func - SFT-lite, task-valid pass@1", diffs_c,
    "table/paragraph currently mean +0.108, SD 0.046 (ddof1)")

# ---- (d) RL-func runs' across-seed SD (task-valid pass@1), quoted as 0.012 ----
res["d_rlfunc3_taskvalid_p1"] = block(
    "RL-func across-seed task-valid pass@1", rlfunc3,
    "paragraph quotes across-seed SD 0.012 ; macro \\tvRlfuncOneS=0.010 (ddof0)")

# ---- (e) gated paired SDs: gated - func, per metric ----
metrics = {
    "taskvalid_p1": "taskvalid_pass@1",
    "verified_p1": "verified_pass@1",
    "taskvalid_p10": "taskvalid_pass@10",
    "verified_p10": "verified_pass@10",
}
gated_current = {  # current (ddof1) paper values, for the sanity check
    "taskvalid_p1": (0.011, 0.023),
    "verified_p1": (0.029, 0.005),
    "taskvalid_p10": (0.015, 0.026),
    "verified_p10": (0.061, 0.069),
}
for tag, key in metrics.items():
    g = summ("results/exp_gated", "rlgated_sftlite", [0, 1, 2], key)
    f = summ("results/exp1b", "rlfunc_sftlite", [0, 1, 2], key)
    diffs = [gi - fi for gi, fi in zip(g, f)]
    b = block(f"gated - func paired diff, {key}", diffs,
              f"current paper mean {gated_current[tag][0]}, SD {gated_current[tag][1]} (ddof1)")
    b["gated_values"] = [round(x, 4) for x in g]
    b["func_values"] = [round(x, 4) for x in f]
    res[f"e_gated_{tag}"] = b

os.makedirs(os.path.join(REPO, "results"), exist_ok=True)
with open(os.path.join(REPO, "results/sd_convention_fix.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, indent=1)

# ---- human-readable summary ----
print("=== SD convention fix (ddof0 population SD is the paper convention) ===\n")
for k, v in res.items():
    print(f"[{k}] {v['label']}")
    print(f"    values={v['values']}  mean={v['mean']}")
    print(f"    ddof0(pop)={v['sd_pop_ddof0']}   ddof1(samp)={v['sd_samp_ddof1']}")
    print(f"    note: {v['note']}\n")
print("wrote results/sd_convention_fix.json")
