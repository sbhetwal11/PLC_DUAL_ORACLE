"""Command-line entry: validate / stats / check-tools / run.

    python -m plcbench.cli validate
    python -m plcbench.cli stats
    python -m plcbench.cli check-tools
    python -m plcbench.cli run [--task <ID>]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from . import __version__
from .backends import compile_matiec, verify_nuxmv
from .harness import evaluate_loaded
from .loader import load_all, load_task, iter_task_dirs


def cmd_validate(_args) -> int:
    ok = True
    n = 0
    for d in iter_task_dirs():
        n += 1
        try:
            lt = load_task(d)
            # cross-check: every var referenced in a property exists in interface
            names = {v.name for v in lt.task.interface}
            for p in lt.task.safety_properties:
                formula = (p.ltl or "") + " " + (p.ctl or "")
                for tok in _idents(formula):
                    if tok in _LTL_KEYWORDS:
                        continue
                    if tok not in names and not tok.isdigit():
                        print(f"  ! {lt.id}: property {p.id} references unknown var '{tok}'")
                        ok = False
            print(f"  ok  {lt.id}  ({lt.task.difficulty.value}, {len(lt.task.safety_properties)} props)")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"  ERR {d.name}: {e}")
    print(f"\n{'PASS' if ok else 'FAIL'}: {n} task(s) checked")
    return 0 if ok else 1


def cmd_stats(_args) -> int:
    tasks = load_all()
    by_tier = Counter(t.task.difficulty.value for t in tasks)
    n_props = sum(len(t.task.safety_properties) for t in tasks)
    by_domain = Counter(t.task.domain for t in tasks)
    print(f"tasks:      {len(tasks)}")
    print(f"by tier:    {dict(by_tier)}")
    print(f"properties: {n_props}")
    print(f"by domain:  {dict(by_domain)}")
    return 0


def cmd_check_tools(_args) -> int:
    print(f"plcbench {__version__}")
    print(f"  MATIEC (iec2c): {'available' if compile_matiec.matiec_available() else 'NOT available'}")
    print(f"  nuXmv:          {'available' if verify_nuxmv.nuxmv_available() else 'NOT available'}")
    if not compile_matiec.matiec_available() or not verify_nuxmv.nuxmv_available():
        print("  -> Phase B: build toolchain/Dockerfile to enable real compile + model-check.")
    return 0


def cmd_run(args) -> int:
    tasks = load_all()
    if args.task:
        tasks = [t for t in tasks if t.id == args.task]
        if not tasks:
            print(f"no task with id {args.task!r}")
            return 1
    for lt in tasks:
        ev = evaluate_loaded(lt)
        print(ev.summary())
    return 0


def cmd_eval_llm(args) -> int:
    import json as _json
    import os
    from .generate.clients import make_generator
    from .generate.evaluate import run_eval

    gen = make_generator(args.model)
    if not gen.available():
        print(f"generator {gen.name!r} is unavailable (missing API key in env?).")
        return 1
    rep = run_eval(gen)
    for r in rep.rows:
        status = (r.error or f"{r.category:18s} props={r.n_props_pass}/{r.n_props} "
                  f"scen={r.scenarios_pass}/{r.scenarios_total}")
        print(f"  {r.task_id:32s} [{r.difficulty:6s}] {status}")
    print("\nSUMMARY:", _json.dumps(rep.summary()))
    print("BY TIER (verified rate):", _json.dumps(rep.by_tier()))
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            _json.dump({"summary": rep.summary(), "by_tier": rep.by_tier(),
                        "rows": [r.__dict__ for r in rep.rows]}, f, indent=2)
        print("wrote", args.out)
    return 0


def cmd_eval_passk(args) -> int:
    import json as _json
    import os
    from .generate.clients import make_generator
    from .generate.evaluate import run_eval_passk

    gen = make_generator(args.model)
    if not gen.available():
        print(f"generator {gen.name!r} is unavailable (missing API key in env?).")
        return 1
    ks = [int(x) for x in str(args.k).split(",") if x.strip()]
    rep = run_eval_passk(gen, args.n, ks, args.temperature, seed=args.seed)
    for r in rep.rows:
        print(f"  {r.task_id:32s} [{r.difficulty:6s}] verified {r.c_verified}/{r.n}")
    print("\nSUMMARY:", _json.dumps(rep.summary()))
    print("BY TIER:", _json.dumps(rep.by_tier()))
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            _json.dump({"summary": rep.summary(), "by_tier": rep.by_tier(),
                        "rows": [r.__dict__ for r in rep.rows]}, f, indent=2)
        print("wrote", args.out)
    return 0


def cmd_smv(args) -> int:
    from .st.smv import translate_src
    tasks = load_all()
    tasks = [t for t in tasks if t.id == args.task] if args.task else tasks
    if not tasks:
        print(f"no task with id {args.task!r}")
        return 1
    for lt in tasks:
        print(f"# ===== {lt.id} =====")
        print(translate_src(lt.reference_st, lt.task))
    return 0


# --- tiny identifier scanner for the validate cross-check --------------------
_LTL_KEYWORDS = {"G", "F", "X", "U", "R", "AG", "EF", "AF", "EG", "TRUE", "FALSE",
                 "AND", "OR", "NOT", "and", "or", "not"}


def _idents(s: str):
    import re
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="plcbench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    sub.add_parser("check-tools").set_defaults(fn=cmd_check_tools)
    pr = sub.add_parser("run")
    pr.add_argument("--task", default=None)
    pr.set_defaults(fn=cmd_run)
    ps = sub.add_parser("smv")
    ps.add_argument("--task", default=None)
    ps.set_defaults(fn=cmd_smv)
    pe = sub.add_parser("eval-llm")
    pe.add_argument("--model", default="reference",
                    help="reference | anthropic:<m> | openai:<m> | grok:<m> | "
                         "deepseek:<m> | gemini:<m>")
    pe.add_argument("--out", default=None, help="write JSON results to this path")
    pe.set_defaults(fn=cmd_eval_llm)
    pk = sub.add_parser("eval-passk")
    pk.add_argument("--model", default="reference",
                    help="reference | anthropic:<m> | openai:<m> | grok:<m> | gemini:<m>")
    pk.add_argument("--n", type=int, default=5, help="samples per task")
    pk.add_argument("--k", default="1,3,5", help="comma-separated k values")
    pk.add_argument("--temperature", type=float, default=0.8)
    pk.add_argument("--seed", type=int, default=None, help="seed RNG before sampling")
    pk.add_argument("--out", default=None)
    pk.set_defaults(fn=cmd_eval_passk)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
