"""Model-sampled candidate pool for the filtering ablation (DeepReview B3).

The procedural references all verify (reject rate 0), so filtering them is inert.
To actually isolate the verifier FILTER's contribution, we build a rejectable pool
the way "verifier-filtered SFT" really works: sample K completions from the BASE
policy for each training-family spec, score each with the dual oracle, and keep the
raw (spec -> model completion) pairs WITH their per-dimension verdicts.

From this pool, make_ablation_datasets (in finetune.build_pool) derives the five
matched SFT sets: all / matiec_only / property_only / dual / random_sizematched.
Each SFT completion is the MODEL's own sample (STaR / rejection-sampling style), so
"dual" trains on verified samples and "all" trains on everything including broken
code - the contrast that measures the filter.

Run on the GPU box (needs the base model) in the toolchain env (nuXmv + MATIEC):
    python -m finetune.build_model_pool --model hf:Qwen/Qwen2.5-Coder-7B-Instruct \
        --k 4 --out finetune/data/pool_model.jsonl
"""
from __future__ import annotations

import argparse
import json
import os

from plcbench.schema import Task
from plcbench.harness import evaluate
from plcbench.generate.prompt import build_prompt
from plcbench.generate.evaluate import _seed_everything
from plcbench.generate.clients import make_generator
from finetune.datagen import generate_all
from finetune.scenarios import synth_scenarios


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="hf:Qwen/Qwen2.5-Coder-7B-Instruct")
    ap.add_argument("--k", type=int, default=4, help="samples per family spec")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="cap #family specs (0=all)")
    ap.add_argument("--out", default="finetune/data/pool_model.jsonl")
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    _seed_everything(args.seed)
    gen = make_generator(args.model)
    if not gen.available():
        print(f"generator {gen.name!r} unavailable"); return 1

    specs = list(generate_all())
    if args.limit:
        specs = specs[:args.limit]
    n = len(specs)
    rows = []
    from collections import Counter
    tally = Counter()
    with open(args.out, "w", encoding="utf-8") as f:
        for i, (meta, ref) in enumerate(specs):
            scs = synth_scenarios(meta, ref)
            meta = {**meta, "scenarios": scs}
            task = Task.model_validate(meta)
            prompt = build_prompt(task)
            try:
                cands = gen.generate_many_text(prompt, args.k, temperature=args.temperature)
            except Exception as e:  # noqa: BLE001
                print(f"  [{i+1}/{n}] {task.id} GEN FAIL {e}"); continue
            kept = 0
            for code in cands:
                ev = evaluate(task, code)
                comp = ev.compiles is True
                # compile-INDEPENDENT property signal (B3): all model-checked props
                # hold regardless of MATIEC, so property_only != dual (a program can
                # model-check TRUE yet fail the compiler -- the gpt-4o case).
                inv = ev.n_props > 0 and ev.n_props_pass == ev.n_props
                scen = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
                tally["total"] += 1
                tally["compile"] += comp; tally["invariant"] += inv; tally["scenario"] += scen
                tally["dual"] += comp and inv
                f.write(json.dumps({"id": task.id, "difficulty": task.difficulty.value,
                                    "prompt": prompt, "completion": code, "meta": meta,
                                    "compile": comp, "invariant": inv, "scenario": scen}) + "\n")
                kept += 1
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{n}] pool={tally['total']} dual={tally['dual']} "
                      f"compile={tally['compile']} inv={tally['invariant']}")
    print("POOL TALLY:", json.dumps(dict(tally)))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
