"""Build the pre-filter candidate pool for the filtering ablation (DeepReview B3).

Runs the FULL procedural generator (datagen.generate_all) and, for every candidate,
records the dual-oracle verdict on each dimension (MATIEC compile / formal
invariants / functional scenarios). Synthesised functional scenarios are attached
to each candidate's meta so downstream task-valid rewards/filters have a signal.

Output: finetune/data/pool.jsonl, one row per candidate:
  {id, difficulty, prompt, completion, meta(+scenarios), compile, invariant, scenario}

From this single pool, make_ablation_datasets() derives the five matched SFT sets:
  all / matiec_only / property_only / dual / random_sizematched.

Run in the toolchain env (NUXMV_BIN + MATIEC_IEC2C).
"""
from __future__ import annotations

import argparse
import json
import os
import random
from collections import Counter

from plcbench.schema import Task
from plcbench.harness import evaluate
from plcbench.generate.prompt import build_prompt
from finetune.datagen import generate_all
from finetune.scenarios import synth_scenarios


def build_pool(out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows = []
    for meta, st in generate_all():
        scs = synth_scenarios(meta, st)
        meta = {**meta, "scenarios": scs}
        task = Task.model_validate(meta)
        ev = evaluate(task, st)
        compile_ok = ev.compiles is True
        # compile-INDEPENDENT property signal so property_only != dual (B3)
        invariant_ok = ev.n_props > 0 and ev.n_props_pass == ev.n_props
        scenario_ok = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
        rows.append({
            "id": task.id, "difficulty": task.difficulty.value,
            "prompt": build_prompt(task), "completion": st, "meta": meta,
            "compile": compile_ok, "invariant": invariant_ok, "scenario": scenario_ok,
        })
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows


def composition(rows):
    n = len(rows)
    comp = Counter()
    comp["total"] = n
    comp["compile_pass"] = sum(r["compile"] for r in rows)
    comp["invariant_pass"] = sum(r["invariant"] for r in rows)
    comp["scenario_pass"] = sum(r["scenario"] for r in rows)
    comp["dual_pass"] = sum(r["compile"] and r["invariant"] for r in rows)
    comp["taskvalid_pass"] = sum(r["compile"] and r["invariant"] and r["scenario"] for r in rows)
    # failure composition among rejects (fail dual)
    rej = [r for r in rows if not (r["compile"] and r["invariant"])]
    comp["reject_total"] = len(rej)
    comp["reject_compile_only"] = sum((not r["compile"]) and r["invariant"] for r in rej)
    comp["reject_invariant_only"] = sum(r["compile"] and (not r["invariant"]) for r in rej)
    comp["reject_both"] = sum((not r["compile"]) and (not r["invariant"]) for r in rej)
    comp["reject_rate"] = round(len(rej) / n, 4) if n else 0.0
    return dict(comp)


def make_ablation_datasets(rows, outdir, seed=0):
    os.makedirs(outdir, exist_ok=True)

    def emit(name, subset):
        path = os.path.join(outdir, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in subset:
                f.write(json.dumps({"id": r["id"], "difficulty": r["difficulty"],
                                    "kind": "zeroshot", "prompt": r["prompt"],
                                    "completion": r["completion"], "meta": r["meta"]}) + "\n")
        return len(subset)

    sets = {
        "all": rows,
        "matiec_only": [r for r in rows if r["compile"]],
        "property_only": [r for r in rows if r["invariant"]],
        "dual": [r for r in rows if r["compile"] and r["invariant"]],
    }
    rng = random.Random(seed)
    dual_n = len(sets["dual"])
    rand = rng.sample(rows, min(dual_n, len(rows)))
    sets["random_sizematched"] = rand
    counts = {name: emit(name, sub) for name, sub in sets.items()}
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="finetune/data/pool.jsonl")
    ap.add_argument("--outdir", default="finetune/data/ablation")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--summary", default="results/exp2/composition.json")
    args = ap.parse_args(argv)

    rows = build_pool(args.pool)
    comp = composition(rows)
    counts = make_ablation_datasets(rows, args.outdir, seed=args.seed)
    print("pool composition:", json.dumps(comp, indent=1))
    print("dataset sizes:", json.dumps(counts, indent=1))
    os.makedirs(os.path.dirname(args.summary) or ".", exist_ok=True)
    with open(args.summary, "w", encoding="utf-8") as f:
        json.dump({"composition": comp, "dataset_sizes": counts,
                   "pool": args.pool, "outdir": args.outdir, "seed": args.seed}, f, indent=1)
    print("wrote", args.summary)


if __name__ == "__main__":
    main()
