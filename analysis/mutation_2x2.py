"""ITEM 30: reconstruct the invariant-by-scenario 2x2 from results/mutation.json.

results/mutation.json stores, per task and in total (compiling mutants only):
  killed_inv  = #mutants where some invariant now fails
  killed_scen = #mutants where some scenario now fails
  inv_blind   = #mutants that PASS all invariants but FAIL a scenario (scenario-only)
  survived    = #mutants that pass BOTH dimensions (neither)
  compiling   = total compiling mutants
These pin the full 2x2 exactly (no raw per-mutant table needed):
  both      = killed_scen - inv_blind      (killed by scenarios AND invariants)
  inv_only  = killed_inv  - both           (killed by invariants only)
  scen_only = inv_blind
  neither   = survived
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

d = json.load(open("results/mutation.json", encoding="utf-8"))
t = d["totals"]
both = t["killed_scen"] - t["inv_blind"]
inv_only = t["killed_inv"] - both
scen_only = t["inv_blind"]
neither = t["survived"]
total = both + inv_only + scen_only + neither

assert total == t["compiling"], (total, t["compiling"])
assert both + inv_only == t["killed_inv"]
assert both + scen_only == t["killed_scen"]

# per-task check that every cell is non-negative (2x2 is consistent per task)
pertask = {}
for tid, r in d["per_task"].items():
    b = r["killed_scen"] - r["inv_blind"]
    io = r["killed_inv"] - b
    pertask[tid] = {"both": b, "inv_only": io, "scen_only": r["inv_blind"],
                    "neither": r["survived"], "total": r["compiling"]}
    assert b >= 0 and io >= 0, (tid, pertask[tid])
    assert b + io + r["inv_blind"] + r["survived"] == r["compiling"], tid

out = {
    "denominator_note": "compiling mutants only (non-compiling mutants excluded)",
    "total_compiling_mutants": t["compiling"],
    "cells": {
        "killed_by_both": both,
        "killed_by_invariants_only": inv_only,
        "killed_by_scenarios_only": scen_only,
        "killed_by_neither_survivors": neither,
    },
    "margins": {
        "killed_by_invariants_total": t["killed_inv"],
        "killed_by_scenarios_total": t["killed_scen"],
        "killed_by_either": both + inv_only + scen_only,
    },
    "raw_per_mutant_outcomes_saved": False,
    "reconstructible_from_aggregates": True,
    "per_task": pertask,
}
json.dump(out, open("results/mutation_2x2.json", "w"), indent=1)

print("== ITEM 30: mutation invariant-by-scenario 2x2 (compiling mutants, N=%d) ==" % total)
print("                       scenario KILLED   scenario SURVIVED   row total")
print(f"invariant KILLED    {both:12d}    {inv_only:15d}   {t['killed_inv']:9d}")
print(f"invariant SURVIVED  {scen_only:12d}    {neither:15d}   {scen_only+neither:9d}")
print(f"col total           {t['killed_scen']:12d}    {inv_only+neither:15d}   {total:9d}")
print()
print(f"  both            = {both}")
print(f"  invariant-only  = {inv_only}")
print(f"  scenario-only   = {scen_only}   (= inv_blind; the metric-validity headline)")
print(f"  neither/survived= {neither}")
print("wrote results/mutation_2x2.json")
