"""Repair-control training sets (DeepReview M19).

Tests whether the counterexample TRACE actually drives counterexample-guided repair
learning, or whether the model infers the fix from the spec + buggy code alone.

From the procedural references (generate_all + generate_hard), we inject bugs using
only the TRAIN mutators (held out from the eval mutator), keep those that genuinely
fail the oracle with a real counterexample, and emit matched repair datasets that
differ ONLY in the feedback channel:

  repair_full      spec + buggy + real counterexample trace   (the method)
  repair_nocex     spec + buggy, no feedback
  repair_proponly  spec + buggy + violated property (no trace)
  repair_erroronly spec + buggy + generic verifier error (no trace)
  repair_shuffle   spec + buggy + a real trace from a DIFFERENT task

Plus generic_sft: a size-matched zero-shot SFT set (no repair pairs) as the
equal-size baseline. All completions are the corrected (verified) reference.

Eval is on HELD-OUT bug types via finetune.eval_repair --mutators <eval-mutator>.

Run in the toolchain env (nuXmv + MATIEC), CPU is fine:
    python -m finetune.build_repair_controls --train-mutators weaken_or,force_true \
        --outdir finetune/data/repair_ctl
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random

from plcbench.schema import Task
from plcbench.harness import evaluate
from plcbench.generate.prompt import build_prompt
from finetune.datagen import generate_all, generate_hard
from finetune import repair as R
from finetune.build_sft import _first_failing
from finetune.scenarios import synth_scenarios

VARIANTS = ["full", "nocex", "proponly", "erroronly", "shuffle"]


def collect_repairs(train_mutators, max_per_task=1):
    """Return list of dicts: {task, base_prompt, bad, pid, nl, cex, completion}."""
    items = []
    for meta, st in itertools.chain(generate_all(), generate_hard()):
        meta = {**meta, "scenarios": synth_scenarios(meta, st)}
        task = Task.model_validate(meta)
        base_prompt = build_prompt(task)
        made = 0
        for bad in R.bug_variants(st, names=train_mutators):
            if made >= max_per_task:
                break
            ev = evaluate(task, bad)
            if ev.verified:
                continue
            fail = _first_failing(task, ev)
            if not fail or not fail[2].strip():
                continue
            pid, nl, cex = fail
            items.append({"id": task.id, "difficulty": task.difficulty.value,
                          "base_prompt": base_prompt, "bad": bad, "pid": pid, "nl": nl,
                          "cex": cex, "completion": st, "meta": meta})
            made += 1
    return items


def emit(outdir, items, seed=0):
    os.makedirs(outdir, exist_ok=True)
    rng = random.Random(seed)
    # precompute a shuffled cex assignment (each item gets another item's cex)
    cexes = [it["cex"] for it in items]
    perm = list(range(len(items)))
    rng.shuffle(perm)
    counts = {}
    for kind in VARIANTS:
        path = os.path.join(outdir, f"repair_{kind}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for i, it in enumerate(items):
                shuf = cexes[perm[i]] if perm[i] != i else cexes[(i + 1) % len(items)]
                prompt = R.variant_prompt(kind, it["base_prompt"], it["bad"], it["pid"],
                                          it["nl"], it["cex"], shuffled_cex=shuf)
                f.write(json.dumps({"id": f"{it['id']}__{kind}", "difficulty": it["difficulty"],
                                    "kind": f"repair_{kind}", "prompt": prompt,
                                    "completion": it["completion"], "meta": it["meta"]}) + "\n")
        counts[kind] = len(items)
    # generic size-matched zeroshot baseline: same tasks, plain spec -> reference
    path = os.path.join(outdir, "generic_sft.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps({"id": it["id"], "difficulty": it["difficulty"],
                                "kind": "zeroshot", "prompt": it["base_prompt"],
                                "completion": it["completion"], "meta": it["meta"]}) + "\n")
    counts["generic_sft"] = len(items)
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-mutators", default="weaken_or,force_true")
    ap.add_argument("--outdir", default="finetune/data/repair_ctl")
    ap.add_argument("--max-per-task", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    train_mut = [m for m in args.train_mutators.split(",") if m]
    items = collect_repairs(train_mut, args.max_per_task)
    counts = emit(args.outdir, items, seed=args.seed)
    print(f"collected {len(items)} repair items (train mutators {train_mut})")
    print("dataset sizes:", json.dumps(counts))
    meta_out = os.path.join(args.outdir, "meta.json")
    json.dump({"train_mutators": train_mut, "n_items": len(items), "counts": counts},
              open(meta_out, "w"), indent=1)
    print("wrote", meta_out)


if __name__ == "__main__":
    main()
