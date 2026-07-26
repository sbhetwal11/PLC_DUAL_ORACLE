"""n=10 API panel re-run WITH raw-completion retention (round-11 item 2).

For each of the 4 frontier models x 22 tasks, samples n=10 completions at
temperature 0.8 (same protocol as the June 2026 pass@k run), but this time:
  - every raw completion (extracted ST) is SAVED to disk,
  - every sample is scored on all oracle dimensions:
      compile (MATIEC), invariant (nuXmv), scenario (interpreter),
      task-valid = compile AND invariant AND scenario,
  - results are written incrementally per task (crash-safe / resumable).

This is a NEW access window (July 2026): the grok-3 slug is served by grok-4.3
(reasoning_effort=none) after 15 May 2026, and other providers may have shifted
behind their slugs. Report as a second panel, not a patch of the June numbers.

Run under the WSL harness:
  wsl bash toolchain/wsl_analysis.sh analysis/api_panel_n10.py [model_spec ...]
"""
from __future__ import annotations
import json, os, sys, time, datetime
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all
from plcbench import harness
from plcbench.generate.clients import make_generator

MODELS = [
    "grok:grok-3",
    "anthropic:claude-sonnet-4-6",
    "gemini:gemini-2.5-flash",
    "openai:gpt-4o",
]
N = 10
TEMP = 0.8
OUTDIR = "results/frontier_n10"
API_WORKERS = 4          # concurrent API calls within one task
RETRIES = 4


def sample_one(gen, lt, idx):
    delay = 5.0
    for attempt in range(RETRIES):
        try:
            code = gen.generate(lt, temperature=TEMP)
            return {"i": idx, "code": code, "error": None}
        except Exception as e:  # HTTP/network; back off and retry
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
    gen = make_generator(spec)
    if not gen.available():
        print(f"SKIP {spec}: API key not available"); return
    path = os.path.join(OUTDIR, spec.replace(":", "_").replace("/", "_") + ".json")
    if os.path.exists(path):
        doc = json.load(open(path, encoding="utf-8"))
    else:
        doc = {"model_spec": spec, "n": N, "temperature": TEMP,
               "access_window": datetime.date.today().isoformat(),
               "note": ("grok-3 slug served by grok-4.3 (reasoning_effort=none) "
                        "since 2026-05-15" if spec.startswith("grok") else ""),
               "rows": []}
    done = {r["task_id"] for r in doc["rows"]}
    for lt in tasks:
        tid = lt.task.id
        if tid in done:
            print(f"  {spec} {tid}: already done, skip"); continue
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
    print(f"n={N} temp={TEMP} tasks={len(tasks)} models={specs}")
    for spec in specs:
        print(f"==== {spec} ====", flush=True)
        run_model(spec, tasks)
    print("ALL DONE")


if __name__ == "__main__":
    main()
