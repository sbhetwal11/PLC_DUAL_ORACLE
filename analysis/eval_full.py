"""Full n-sample evaluator that SAVES every raw generated program and scores each
on all four dimensions, so pass@k can be computed for BOTH the old invariant-only
"verified" metric AND the construct-valid "task-valid" metric (compile AND all
invariants AND all functional scenarios), per DeepReview B1/B4.

Unlike plcbench.generate.evaluate.run_eval_passk (which only cached counts), this
persists the raw code + per-dimension verdict for each of the n samples per task,
enabling task-valid pass@k, output-activity analysis (Exp8), and failure taxonomy
to be recomputed offline without re-querying the model.

Usage (in the toolchain env with NUXMV_BIN + MATIEC_IEC2C set):
    PYTHONPATH=<repo> python -m analysis.eval_full \
        --model "hf:Qwen/Qwen2.5-Coder-7B-Instruct+finetune/out/full/sftlite_s0" \
        --n 10 --k 1,3,5,10 --temperature 0.8 --seed 0 \
        --out results/exp1a/sftlite_s0.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict

from plcbench.harness import evaluate
from plcbench.loader import load_all
from plcbench.st import STSyntaxError, parse_program
from plcbench.generate.clients import make_generator
from plcbench.generate.evaluate import _seed_everything, _categorize, pass_at_k


def score_sample(task, code: str) -> dict:
    """Evaluate one candidate on every dimension. Returns a dict with the raw code
    and boolean verdicts. task-valid = compile AND all invariants AND all scenarios."""
    ev = evaluate(task, code)
    try:
        parse_program(code)
        parsed = True
    except (STSyntaxError, Exception):  # noqa: BLE001
        parsed = False
    category = _categorize(parsed, ev)
    compile_ok = ev.compiles is True
    invariant_ok = ev.verified is True                      # compile AND all props
    scenario_ok = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
    taskvalid = compile_ok and invariant_ok and scenario_ok
    return {
        "code": code,
        "parsed": parsed,
        "category": category,
        "compile": compile_ok,
        "invariant": invariant_ok,
        "scenario": scenario_ok,
        "taskvalid": taskvalid,
        "n_props": ev.n_props,
        "n_props_pass": ev.n_props_pass,
        "scen_total": ev.scenarios_total,
        "scen_pass": ev.scenarios_pass,
    }


def evaluate_generator(generator, n_samples: int, temperature: float, seed=None,
                       tasks=None, save_code=True):
    if seed is not None:
        _seed_everything(seed)
    tasks = tasks or load_all()
    has_batch = hasattr(generator, "generate_many")
    rows = []
    for lt in tasks:
        samples = []
        codes = None
        if has_batch:
            try:
                codes = generator.generate_many(lt, n_samples, temperature=temperature)
            except Exception:  # noqa: BLE001 (fall back to sequential)
                codes = None
        for i in range(n_samples):
            try:
                code = codes[i] if codes is not None else \
                    generator.generate(lt, temperature=temperature)
            except Exception as e:  # noqa: BLE001 (API/inference failure: skip sample)
                samples.append({"error": str(e)[:200]})
                continue
            s = score_sample(lt.task, code)
            if not save_code:
                s.pop("code", None)
            samples.append(s)
        ok = [s for s in samples if "error" not in s]
        rows.append({
            "task_id": lt.id,
            "difficulty": lt.task.difficulty.value,
            "n": len(ok),
            "c_compile": sum(1 for s in ok if s["compile"]),
            "c_verified": sum(1 for s in ok if s["invariant"]),
            "c_scenario": sum(1 for s in ok if s["scenario"]),
            "c_taskvalid": sum(1 for s in ok if s["taskvalid"]),
            "samples": samples,
        })
    return rows


def aggregate(rows, ks):
    """Compute pass@k for verified (invariant-only) and task-valid, overall + tier."""
    def passk_over(rowset, field, k):
        vals = [pass_at_k(r["n"], r[field], k) for r in rowset if r["n"] > 0]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary = {}
    for metric, field in (("verified", "c_verified"), ("taskvalid", "c_taskvalid"),
                          ("compile", "c_compile"), ("scenario", "c_scenario")):
        for k in ks:
            summary[f"{metric}_pass@{k}"] = passk_over(rows, field, k)
    by_tier = {}
    for tier in ("easy", "medium", "hard"):
        rs = [r for r in rows if r["difficulty"] == tier and r["n"] > 0]
        if not rs:
            continue
        d = {}
        for metric, field in (("verified", "c_verified"), ("taskvalid", "c_taskvalid")):
            for k in ks:
                d[f"{metric}_pass@{k}"] = passk_over(rs, field, k)
        by_tier[tier] = d
    return summary, by_tier


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--k", default="1,3,5,10")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-code", dest="save_code", action="store_false",
                    help="do not persist raw code (smaller JSON)")
    args = ap.parse_args(argv)
    ks = [int(x) for x in str(args.k).split(",") if x.strip()]

    gen = make_generator(args.model)
    if not gen.available():
        print(f"generator {gen.name!r} unavailable")
        return 1
    rows = evaluate_generator(gen, args.n, args.temperature, seed=args.seed,
                              save_code=args.save_code)
    summary, by_tier = aggregate(rows, ks)
    for r in rows:
        print(f"  {r['task_id']:32s} [{r['difficulty']:6s}] "
              f"verified {r['c_verified']}/{r['n']}  taskvalid {r['c_taskvalid']}/{r['n']}")
    print("SUMMARY:", json.dumps(summary))
    out = {"model": gen.name, "n": args.n, "temperature": args.temperature,
           "seed": args.seed, "ks": ks, "summary": summary, "by_tier": by_tier,
           "rows": rows}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
