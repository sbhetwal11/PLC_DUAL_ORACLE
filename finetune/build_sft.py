"""Build an SFT dataset: generate task-family instances, verify each with the
dual oracle (MATIEC compile + nuXmv safety), keep only verified pairs.

Run in the toolchain env (needs nuXmv + MATIEC):
    PYTHONPATH=<repo> python -m finetune.build_sft --out finetune/data/sft.jsonl

Flags:
    --include-hard   also emit the harder v2 families (datagen.generate_hard)
    --repair         also emit counterexample-repair pairs: inject a safety bug,
                     verify it really fails, attach the real nuXmv counterexample,
                     and pair it with the corrected (verified) reference.

Each kept line: {"id","difficulty","kind","prompt","completion","meta"} where
kind is "zeroshot" or "repair". Held out from the 22-task eval benchmark.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os

from plcbench.schema import Task
from plcbench.harness import evaluate
from plcbench.generate.prompt import build_prompt
from finetune.datagen import generate_all, generate_hard
from finetune import repair as repair_mod


def _first_failing(task: Task, ev):
    """Return (property_id, nl, counterexample) for the first refuted property."""
    if not ev.verify or not ev.verify.available:
        return None
    nl_by_id = {p.id: p.nl for p in task.safety_properties}
    for pr in ev.verify.properties:
        if pr.status == "fail":
            return pr.property_id, nl_by_id.get(pr.property_id, ""), (pr.counterexample or "")
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="finetune/data/sft.jsonl")
    ap.add_argument("--include-hard", action="store_true")
    ap.add_argument("--repair", action="store_true")
    ap.add_argument("--max-repair-per-task", type=int, default=1)
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    gens = [generate_all()]
    if args.include_hard:
        gens.append(generate_hard())
    source = itertools.chain(*gens)

    kept = total = repairs = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for meta, st in source:
            total += 1
            task = Task.model_validate(meta)
            ev = evaluate(task, st)
            status = ("verified" if ev.verified
                      else f"compiles={ev.compiles} props={ev.n_props_pass}/{ev.n_props}")
            print(f"  {task.id:30s} {status}")
            if not ev.verified:
                continue
            kept += 1
            base_prompt = build_prompt(task)
            f.write(json.dumps({"id": task.id, "difficulty": task.difficulty.value,
                                "kind": "zeroshot", "prompt": base_prompt,
                                "completion": st, "meta": meta}) + "\n")
            if not args.repair:
                continue
            # counterexample-repair pairs: inject bugs, keep ones that really fail.
            made = 0
            for bad in repair_mod.bug_variants(st):
                if made >= args.max_repair_per_task:
                    break
                bev = evaluate(task, bad)
                if bev.verified:            # mutation didn't break safety -> skip
                    continue
                fail = _first_failing(task, bev)
                if not fail:                # parse/translate error, no real cex -> skip
                    continue
                pid, nl, cex = fail
                if not cex.strip():
                    continue
                rp = repair_mod.repair_prompt(base_prompt, bad, pid, nl, cex)
                f.write(json.dumps({"id": f"{task.id}__repair{made}",
                                    "difficulty": task.difficulty.value, "kind": "repair",
                                    "prompt": rp, "completion": st, "meta": meta}) + "\n")
                made += 1
                repairs += 1
            if made:
                print(f"      +{made} repair pair(s)")
    print(f"\nSFT: kept {kept}/{total} verified zeroshot pairs"
          f"{f' + {repairs} repair pairs' if args.repair else ''} -> {args.out}")
    if kept == 0:
        print("WARNING: 0 kept -- are nuXmv (NUXMV_BIN) and MATIEC (MATIEC_IEC2C) set? "
              "Run this in the toolchain env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
