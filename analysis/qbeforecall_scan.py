"""Blast-radius scan for the translator's read-before-call Q pre-seed defect
(found by the round-12 SMV trace leg): count programs, across every evaluated
set, that read a TON's Q (or self-reference Q in its own IN) before that timer's
call in scan order -- the only construct on which smv.py's constant-FALSE
pre-seed diverges from the interpreter's previous-scan value.

Run: wsl bash toolchain/wsl_analysis.sh analysis/qbeforecall_scan.py  (or plain python)
"""
from __future__ import annotations
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.st.parser import (Assign, Binary, Case, If, TimerCall, Unary, Var,
                                parse_program)


def reads_q_before_call(src) -> bool:
    try:
        prog = parse_program(src)
    except Exception:
        return False
    timers = {d.name for d in prog.decls if d.type == "TON"}
    if not timers:
        return False
    called = set()
    hit = [False]

    def expr(e):
        if isinstance(e, Var):
            if "." in e.name:
                base, mem = e.name.split(".", 1)
                if base in timers and mem.upper() == "Q" and base not in called:
                    hit[0] = True
        elif isinstance(e, Unary):
            expr(e.operand)
        elif isinstance(e, Binary):
            expr(e.left); expr(e.right)

    def walk(stmts):
        for s in stmts:
            if isinstance(s, Assign):
                expr(s.expr)
            elif isinstance(s, TimerCall):
                expr(s.in_expr)          # self/other reads before this call registers
                expr(s.pt)
                called.add(s.instance)
            elif isinstance(s, If):
                for c, b in s.branches:
                    expr(c); walk(b)
                walk(s.orelse)
            elif isinstance(s, Case):
                expr(s.selector)
                for _, b in s.branches:
                    walk(b)
                walk(s.orelse)

    walk(prog.body)
    return hit[0]


def scan_jsonl_field(path, getcode):
    n = tot = 0
    for line in open(path, encoding="utf-8"):
        code = getcode(json.loads(line))
        if not code:
            continue
        tot += 1
        if reads_q_before_call(code):
            n += 1
    return n, tot


def main():
    # references
    n = t = 0
    for p in sorted(glob.glob("benchmark/tasks/*/*/reference.st")):
        t += 1
        if reads_q_before_call(open(p, encoding="utf-8").read()):
            n += 1
            print("  REF AFFECTED:", p)
    print(f"references: {n}/{t}")

    # SFT corpora
    for f in ["finetune/data/sft.jsonl", "finetune/data/sft_v2.jsonl",
              "finetune/data/sft_zeroshot.jsonl"]:
        if os.path.exists(f):
            n, t = scan_jsonl_field(f, lambda d: d.get("completion") or d.get("output")
                                    or d.get("response") or d.get("st") or "")
            print(f"{f}: {n}/{t}")

    # trained-model samples (exp1a + exp1b): the canonical released programs
    for pat, label in [("results/exp1a/*_s*.json", "exp1a"),
                       ("results/exp1b/*_s*.json", "exp1b")]:
        n = t = flip_candidates = 0
        for f in sorted(glob.glob(pat)):
            d = json.load(open(f, encoding="utf-8"))
            for row in d["rows"]:
                for s in row["samples"]:
                    code = (s.get("code") or "").strip()
                    if not code:
                        continue
                    t += 1
                    if reads_q_before_call(code):
                        n += 1
                        if s.get("invariant") or s.get("taskvalid"):
                            flip_candidates += 1
        print(f"{label} samples: {n}/{t} affected "
              f"({flip_candidates} of them currently scored invariant/task-valid)")

    # July API panel
    n = t = flip = 0
    for f in sorted(glob.glob("results/frontier_n10/*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for row in d["rows"]:
            for s in row["samples"]:
                code = (s.get("code") or "").strip()
                if not code:
                    continue
                t += 1
                if reads_q_before_call(code):
                    n += 1
                    if s.get("invariant") or s.get("taskvalid"):
                        flip += 1
    print(f"July n=10 API panel samples: {n}/{t} affected ({flip} scored inv/TV)")

    # June single-sample panel
    n = t = 0
    for f in ["results/grok_grok-3.json", "results/anthropic_claude-sonnet-4-6.json",
              "results/gemini_gemini-2.5-flash.json", "results/openai_gpt-4o.json"]:
        if not os.path.exists(f):
            continue
        d = json.load(open(f, encoding="utf-8"))
        for r in d["rows"]:
            code = (r.get("code") or "").strip()
            if code:
                t += 1
                if reads_q_before_call(code):
                    n += 1
    print(f"June single-sample panel: {n}/{t} affected")


if __name__ == "__main__":
    main()
