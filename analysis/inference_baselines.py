"""Inference-time verifier baselines vs verifier-trained models (DeepReview B7).

Two cost-matched inference strategies that use the oracle at test time instead of
in training:

  best-of-k : sample k completions, let the oracle SELECT one; success iff >=1 of
              the k is task-valid. Oracle budget = k model-checker/compiler runs.
  repair-R  : sample 1; if not task-valid, feed the real nuXmv counterexample back
              and resample a fix; iterate up to R rounds. Oracle budget <= R.

Both are run from a given hf policy (base or SFT). Compared against the verifier-
TRAINED policies' pass@1/pass@k (from analysis.eval_full), this isolates whether
training beats merely using the same oracle at inference under a matched budget.

Criterion is TASK-VALID (compile AND invariants AND scenarios), per B1/B4.

    python -m analysis.inference_baselines --model hf:Qwen/Qwen2.5-Coder-7B-Instruct \
        --k 10 --repair 5 --seed 0 --out results/exp7/base_infer_s0.json
"""
from __future__ import annotations

import argparse
import json
import os

from plcbench.harness import evaluate
from plcbench.loader import load_all
from plcbench.generate.prompt import build_prompt
from plcbench.generate.clients import make_generator
from plcbench.generate.evaluate import _seed_everything
from finetune.repair import repair_prompt


def _taskvalid(ev):
    return (ev.compiles is not False) and (ev.verified is True) and \
           ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total


def _first_fail(task, ev):
    if not ev.verify or not ev.verify.available:
        return None
    nl = {p.id: p.nl for p in task.safety_properties}
    for pr in ev.verify.properties:
        if pr.status == "fail":
            return pr.property_id, nl.get(pr.property_id, ""), (pr.counterexample or "")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="hf:<model>[+adapter]")
    ap.add_argument("--k", type=int, default=10, help="best-of-k budget")
    ap.add_argument("--repair", type=int, default=5, help="max repair rounds")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    _seed_everything(args.seed)
    gen = make_generator(args.model)
    if not gen.available():
        print(f"generator {gen.name!r} unavailable"); return 1

    tasks = load_all()
    bo_rows, rp_rows = [], []
    for lt in tasks:
        task = lt.task
        prompt = build_prompt(task)
        # ---- best-of-k (batched) ----
        cands = gen.generate_many_text(prompt, args.k, temperature=args.temperature)
        bo_ok = False; bo_calls = 0
        for code in cands:
            bo_calls += 1
            if _taskvalid(evaluate(task, code)):
                bo_ok = True
                break
        bo_rows.append({"task_id": task.id, "difficulty": task.difficulty.value,
                        "success": bo_ok, "oracle_calls": bo_calls})
        # ---- iterative counterexample-guided repair ----
        cur_prompt = prompt
        rp_ok = False; rounds = 0
        for r in range(args.repair):
            rounds += 1
            code = gen.generate_text(cur_prompt, temperature=args.temperature)
            ev = evaluate(task, code)
            if _taskvalid(ev):
                rp_ok = True
                break
            fail = _first_fail(task, ev)
            if not fail or not fail[2].strip():
                # no counterexample to feed (e.g. compile/translate failure): retry fresh
                cur_prompt = prompt
                continue
            pid, nl, cex = fail
            cur_prompt = repair_prompt(prompt, code, pid, nl, cex)
        rp_rows.append({"task_id": task.id, "difficulty": task.difficulty.value,
                        "success": rp_ok, "oracle_calls": rounds})
        print(f"  {task.id:30s} best-of-{args.k}={'Y' if bo_ok else 'n'}({bo_calls}) "
              f"repair={'Y' if rp_ok else 'n'}({rounds})")

    def summ(rows):
        n = len(rows)
        return {"success_rate": round(sum(r["success"] for r in rows) / n, 4),
                "mean_oracle_calls": round(sum(r["oracle_calls"] for r in rows) / n, 3),
                "total_oracle_calls": sum(r["oracle_calls"] for r in rows), "tasks": n}

    out = {"model": args.model, "seed": args.seed, "k": args.k, "repair_rounds": args.repair,
           "best_of_k": {**summ(bo_rows), "rows": bo_rows},
           "repair": {**summ(rp_rows), "rows": rp_rows}}
    print("best-of-k:", json.dumps({k: v for k, v in out["best_of_k"].items() if k != "rows"}))
    print("repair   :", json.dumps({k: v for k, v in out["repair"].items() if k != "rows"}))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=1)
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
