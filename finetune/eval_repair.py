"""Counterexample-guided REPAIR evaluation.

Directly tests the method's signature capability: given a spec, a *failing* program,
and the formal counterexample, can the model return a verified-safe fix? Distinct
from the zero-shot generation benchmark.

Build (once, deterministic): for each of the 22 eval tasks, take the verified
reference, inject a real safety bug (finetune.repair), confirm it actually fails
nuXmv, and record (spec + buggy code + real counterexample) as the repair prompt.
Saved to finetune/data/repair_eval.jsonl so every model is scored on the SAME set.

Eval: for an hf model, sample n fixes per prompt, score each with the dual oracle
(verified == compiles ∧ all properties hold), report repair pass@k.

    # build the fixed set (needs nuXmv + MATIEC):
    python -m finetune.eval_repair --build
    # score a model:
    python -m finetune.eval_repair --model "hf:Qwen/Qwen2.5-Coder-7B-Instruct+finetune/out/v2/sft_s0" \
        --n 10 --k 1,3,5,10 --seed 0 --out results/full/repair_<tag>.json
"""
from __future__ import annotations

import argparse
import json
import math
import os

from plcbench.schema import Task
from plcbench.loader import LoadedTask, load_all
from plcbench.generate.prompt import build_prompt
from plcbench.generate.clients import make_generator
from plcbench.generate.evaluate import _seed_everything
from finetune.reward import dual_oracle_reward, task_valid_reward
from finetune import repair as repair_mod
from finetune.build_sft import _first_failing

REPAIR_SET = "finetune/data/repair_eval.jsonl"


def build_repair_set(out_path: str = REPAIR_SET, mutators=None) -> int:
    """For each eval task, make one (spec+buggy+counterexample) repair prompt.

    mutators: optional subset of bug types (held-out-bug-type eval, M19)."""
    from plcbench.harness import evaluate
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    kept = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for lt in load_all():
            task = lt.task
            for bad in repair_mod.bug_variants(lt.reference_st, names=mutators):
                bev = evaluate(task, bad)
                if bev.verified:                 # mutation didn't break safety
                    continue
                fail = _first_failing(task, bev)
                if not fail:
                    continue
                pid, nl, cex = fail
                if not (cex or "").strip():
                    continue
                prompt = repair_mod.repair_prompt(build_prompt(task), bad, pid, nl, cex)
                f.write(json.dumps({"task_id": task.id,
                                    "difficulty": task.difficulty.value,
                                    "prompt": prompt, "meta": task.model_dump(mode="json")}) + "\n")
                kept += 1
                break
    print(f"repair set: {kept} tasks with a real counterexample -> {out_path}")
    return kept


def _passk(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="build the repair set and exit")
    ap.add_argument("--model", default=None, help="hf:<model>[+<adapter>]")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--k", default="1,3,5,10")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--set", default=REPAIR_SET)
    ap.add_argument("--mutators", default=None, help="comma subset for held-out-bug eval")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    muts = [m for m in args.mutators.split(",")] if args.mutators else None

    if args.build or not os.path.exists(args.set):
        build_repair_set(args.set, mutators=muts)
        if args.build:
            return 0

    if not args.model:
        print("no --model given; repair set is ready at", args.set)
        return 0
    if not args.model.startswith("hf:"):
        print("repair eval supports hf: models only"); return 1

    _seed_everything(args.seed)
    gen = make_generator(args.model)
    if not gen.available():
        print(f"generator {gen.name!r} unavailable"); return 1

    rows = [json.loads(l) for l in open(args.set, encoding="utf-8") if l.strip()]
    ks = [int(x) for x in str(args.k).split(",") if x.strip()]
    per_task = []
    for r in rows:
        meta = r["meta"]
        c = nrun = 0
        # batched sampling of the n fixes for this prompt (much faster than n serial
        # generate_text calls); fall back to sequential if the generator lacks it.
        fixes = None
        if hasattr(gen, "generate_many_text"):
            try:
                fixes = gen.generate_many_text(r["prompt"], args.n, temperature=args.temperature)
            except Exception:  # noqa: BLE001
                fixes = None
        for i in range(args.n):
            try:
                fix = fixes[i] if fixes is not None else \
                    gen.generate_text(r["prompt"], temperature=args.temperature)
            except Exception:  # noqa: BLE001
                continue
            nrun += 1
            if task_valid_reward(meta, fix) >= 0.999:   # task-valid fix (B1/B4)
                c += 1
        per_task.append({"task_id": r["task_id"], "difficulty": r["difficulty"],
                         "n": nrun, "c_verified": c})
        print(f"  {r['task_id']:32s} repaired {c}/{nrun}")

    summary = {"model": args.model, "n_samples": args.n, "temperature": args.temperature,
               "tasks": len(per_task)}
    for k in ks:
        vals = [_passk(t["n"], t["c_verified"], k) for t in per_task if t["n"] >= k]
        summary[f"pass@{k}"] = round(sum(vals) / len(vals), 4) if vals else 0.0
    tiers = {}
    for t in per_task:
        tiers.setdefault(t["difficulty"], []).append(t)
    by_tier = {d: {f"pass@{k}": round(sum(_passk(x["n"], x["c_verified"], k)
                                          for x in ts if x["n"] >= k)
                                      / max(1, len([x for x in ts if x["n"] >= k])), 4)
                   for k in ks} for d, ts in tiers.items()}
    print("\nSUMMARY:", json.dumps(summary))
    print("BY TIER:", json.dumps(by_tier))
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump({"summary": summary, "by_tier": by_tier, "rows": per_task},
                  open(args.out, "w", encoding="utf-8"), indent=2)
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
