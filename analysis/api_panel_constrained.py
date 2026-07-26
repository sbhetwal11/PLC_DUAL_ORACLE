"""Harness-constrained prompt mode for the API panel (round-12 item 15).

Identical protocol to analysis/api_panel_n10.py (n=10, temperature 0.8, all raw
completions retained, per-task incremental save, resumable) with ONE difference:
the prompt appends an explicit statement of the accepted ST subset, so models are
not penalized for guessing hidden harness restrictions. The July open-mode panel
(results/frontier_n10/) is the paired IEC-open condition.

Run: wsl bash -c "source ~/.plcbench_env; bash toolchain/wsl_analysis.sh analysis/api_panel_constrained.py [model ...]"
"""
from __future__ import annotations
import datetime
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness
from plcbench.generate import clients as _clients
from plcbench.generate.prompt import build_prompt as _open_prompt

SUBSET_BLOCK = """
IMPORTANT - the verification toolchain accepts ONLY this IEC 61131-3 ST subset.
Stay strictly within it:
- One PROGRAM ... END_PROGRAM block; VAR_INPUT / VAR_OUTPUT / VAR sections.
- Scalar BOOL and INT variables only (optional literal initializers). No arrays,
  REAL, TIME variables, STRING, enumerations, structs, or RETAIN.
- Statements: assignments (:=), IF/ELSIF/ELSE/END_IF, CASE ... OF with integer
  labels and optional ELSE ... END_CASE.
- Expressions: AND, OR, NOT, comparisons (=, <>, <, <=, >, >=), integer
  +, -, *, MOD. Keep INT values inside the ranges implied by the interface.
- Timers: TON only (no TP, TOF, counters, or other function blocks). Declare
  instances in VAR, call each exactly once per scan, unconditionally, at the top
  level of the program body (never inside IF/CASE), as
  Name(IN := <bool expr>, PT := T#<N>s); with a whole-second literal preset.
  Gate timing through the IN expression. Read results as Name.Q / Name.ET.
- No user-defined functions or function blocks, no vendor extensions, no direct
  addressing (%I/%Q), no pointers.
"""


def constrained_prompt(task) -> str:
    return _open_prompt(task) + SUBSET_BLOCK


_clients.build_prompt = constrained_prompt   # generators resolve prompt via module global

MODELS = [
    "gemini:gemini-2.5-flash",
    "grok:grok-3",
    "openai:gpt-4o",
    "anthropic:claude-sonnet-4-6",
]
N = 10
TEMP = 0.8
OUTDIR = "results/frontier_n10_constrained"
API_WORKERS = 4
RETRIES = 4


def sample_one(gen, lt, idx):
    delay = 5.0
    err = None
    for _ in range(RETRIES):
        try:
            return {"i": idx, "code": gen.generate(lt, temperature=TEMP), "error": None}
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(delay)
            delay *= 2
    return {"i": idx, "code": "", "error": err}


def score(lt, code):
    if not code.strip():
        return {"compile": False, "invariant": False, "scenario": False,
                "taskvalid": False, "empty": True}
    ev = harness.evaluate(lt.task, code)
    c = ev.compiles is True
    i = ev.verified is True
    s = ev.scenarios_total > 0 and ev.scenarios_pass == ev.scenarios_total
    return {"compile": c, "invariant": i, "scenario": s,
            "taskvalid": c and i and s, "empty": False}


def run_model(spec, tasks):
    gen = _clients.make_generator(spec)
    if not gen.available():
        print(f"SKIP {spec}: no API key"); return
    path = os.path.join(OUTDIR, spec.replace(":", "_").replace("/", "_") + ".json")
    if os.path.exists(path):
        doc = json.load(open(path, encoding="utf-8"))
    else:
        doc = {"model_spec": spec, "n": N, "temperature": TEMP,
               "prompt_mode": "harness-constrained",
               "access_window": datetime.date.today().isoformat(),
               "note": ("grok-3 slug served by grok-4.3 (reasoning_effort=none) "
                        "since 2026-05-15" if spec.startswith("grok") else ""),
               "rows": []}
    done = {r["task_id"] for r in doc["rows"]}
    for lt in tasks:
        tid = lt.task.id
        if tid in done:
            print(f"  {spec} {tid}: done, skip"); continue
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=API_WORKERS) as ex:
            samples = list(ex.map(lambda i: sample_one(gen, lt, i), range(N)))
        samples.sort(key=lambda s: s["i"])
        for s in samples:
            s.update(score(lt, s["code"]))
        row = {"task_id": tid, "difficulty": lt.task.difficulty.value,
               "samples": samples,
               "c_compile": sum(s["compile"] for s in samples),
               "c_verified": sum(s["invariant"] for s in samples),
               "c_scenario": sum(s["scenario"] for s in samples),
               "c_taskvalid": sum(s["taskvalid"] for s in samples),
               "n_errors": sum(1 for s in samples if s["error"])}
        doc["rows"].append(row)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
        os.replace(tmp, path)
        print(f"  {spec} {tid}: compile {row['c_compile']}/{N} "
              f"inv {row['c_verified']}/{N} scen {row['c_scenario']}/{N} "
              f"TV {row['c_taskvalid']}/{N} err {row['n_errors']} "
              f"({time.time()-t0:.0f}s)", flush=True)
    print(f"DONE {spec} -> {path}")


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    tasks = sorted(load_all(), key=lambda lt: lt.task.id)
    specs = sys.argv[1:] or MODELS
    print(f"CONSTRAINED mode n={N} temp={TEMP} tasks={len(tasks)} models={specs}")
    for spec in specs:
        print(f"==== {spec} ====", flush=True)
        run_model(spec, tasks)
    print("ALL DONE")


if __name__ == "__main__":
    main()
