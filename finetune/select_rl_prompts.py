"""Failure-frequency RL prompt selection.

Naive verifier-reward GRPO stalls when every sampled completion already verifies
(zero reward variance -> zero advantage). This script samples the *policy we will
warm-start from* on a pool of candidate tasks, scores each sample with the dual
oracle, and keeps the prompts whose verified-fraction is strictly between 0 and 1
-- i.e. the model's *capability frontier*, where GRPO groups have non-zero reward
variance and therefore a learning signal. Output is an RL prompt file (prompt+meta).

Run in the toolchain env (nuXmv + MATIEC) on the GPU box, e.g.:
    python -m finetune.select_rl_prompts \
        --model "hf:Qwen/Qwen2.5-Coder-7B-Instruct+finetune/out/sft_v2" \
        --n 6 --keep 64 --out finetune/data/rl_prompts.jsonl
"""
from __future__ import annotations

import argparse
import json
import os

from statistics import mean, pstdev

from plcbench.schema import Task
from plcbench.loader import LoadedTask
from plcbench.generate.prompt import build_prompt
from plcbench.generate.clients import make_generator
from plcbench.generate.evaluate import _seed_everything
from finetune.datagen import generate_all, generate_hard
from finetune.reward import dual_oracle_reward, task_valid_reward
from finetune.scenarios import synth_scenarios


def _candidates(include_hard: bool, only_hard: bool = False, attach_scen=False):
    import itertools
    if only_hard:
        gens = [generate_hard()]
    else:
        gens = [generate_all()] + ([generate_hard()] if include_hard else [])
    for meta, ref in itertools.chain(*gens):
        if attach_scen:
            meta = {**meta, "scenarios": synth_scenarios(meta, ref)}
        yield meta


def _reward_stats(generator, task: Task, meta: dict, n: int, temperature: float,
                  reward_fn=dual_oracle_reward):
    """Sample n completions and score each with the GRADED reward (the exact RL
    reward). Return (mean_reward, std_reward, verified_fraction)."""
    lt = LoadedTask(task=task, dir=None, reference_st="")
    rewards, verified = [], 0
    # batched sampling when the generator supports it (much faster)
    codes = None
    if hasattr(generator, "generate_many"):
        try:
            codes = generator.generate_many(lt, n, temperature=temperature)
        except Exception:  # noqa: BLE001
            codes = None
    for i in range(n):
        try:
            code = codes[i] if codes is not None else generator.generate(lt, temperature=temperature)
        except Exception:  # noqa: BLE001
            continue
        r = reward_fn(meta, code)
        rewards.append(r)
        if r >= 0.999:           # graded reward == 1.0 iff fully valid
            verified += 1
    if not rewards:
        return 0.0, 0.0, 0.0
    return mean(rewards), pstdev(rewards), verified / len(rewards)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="hf:<model>[+<adapter>] policy to probe")
    ap.add_argument("--n", type=int, default=6, help="samples per candidate")
    ap.add_argument("--keep", type=int, default=64, help="max prompts to keep")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--include-hard", action="store_true", default=True)
    ap.add_argument("--only-hard", action="store_true",
                    help="probe ONLY generate_hard (held out from generate_all SFT)")
    ap.add_argument("--limit", type=int, default=0, help="cap candidates probed (0=all)")
    ap.add_argument("--min-std", type=float, default=0.05,
                    help="keep prompts whose graded-reward std exceeds this")
    ap.add_argument("--reward", choices=["invariant", "taskvalid"], default="invariant")
    ap.add_argument("--out", default="finetune/data/rl_prompts.jsonl")
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    reward_fn = dual_oracle_reward if args.reward == "invariant" else task_valid_reward

    _seed_everything(args.seed)
    gen = make_generator(args.model)
    if not gen.available():
        print(f"generator {gen.name!r} unavailable")
        return 1

    scored = []
    cands = list(_candidates(args.include_hard, args.only_hard,
                             attach_scen=(args.reward == "taskvalid")))
    if args.limit and len(cands) > args.limit:
        # deterministic stride sample so all families are represented
        step = len(cands) / args.limit
        cands = [cands[int(i * step)] for i in range(args.limit)]
    for meta in cands:
        task = Task.model_validate(meta)
        rmean, rstd, frac = _reward_stats(gen, task, meta, args.n, args.temperature,
                                          reward_fn=reward_fn)
        tag = "(keep)" if rstd >= args.min_std else ""
        print(f"  {task.id:30s} reward={rmean:.2f}±{rstd:.2f} verified={frac:.2f} {tag}")
        if rstd >= args.min_std:                    # has graded-reward variance
            scored.append((rstd, rmean, frac, meta))
    scored.sort(key=lambda r: r[0], reverse=True)   # highest reward variance first
    keep = scored[:args.keep]
    with open(args.out, "w", encoding="utf-8") as f:
        for rstd, rmean, frac, meta in keep:
            task = Task.model_validate(meta)
            f.write(json.dumps({"prompt": build_prompt(task), "meta": meta,
                                "reward_mean": round(rmean, 3), "reward_std": round(rstd, 3),
                                "verified_frac": round(frac, 3)}) + "\n")
    print(f"\nselected {len(keep)} frontier prompts (of {len(scored)} with reward variance "
          f">= {args.min_std}) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
