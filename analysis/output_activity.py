"""Output-activity / inert-collapse analysis of trained policies (DeepReview B4).

Consumes the raw programs saved by analysis.eval_full (results/<dir>/<stage>_s<seed>.json)
and, for each condition, reports:
  - functional-scenario pass rate (mean over samples)
  - output-activation frequency: fraction of samples whose outputs are EVER driven
    TRUE across the task scenarios (i.e. the controller actually acts)
  - % of completions equivalent to all-off / all-on / constant-output policies,
    determined behaviourally: run the sample and the degenerate baseline on the
    task scenarios' input sequences and compare the output traces.

This directly tests the claim that verifier-trained policies "never collapse to the
inert program": a high all-off-equivalent fraction would refute it.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict

from plcbench.loader import load_all
from plcbench.st import parse_program, STSyntaxError
from plcbench.st.interp import initial_state, run_scan

_TASKS = {lt.id: lt for lt in load_all()}


def _output_names(task):
    return [v.name for v in task.interface if v.direction.value == "output"]


def _degenerate_body(task, mode):
    outs = [v for v in task.interface if v.direction.value == "output"]
    lines = []
    for v in outs:
        if mode == "all-off":
            val = "FALSE" if v.type == "BOOL" else str(int(v.range[0]) if v.range else 0)
        elif mode == "all-on":
            val = "TRUE" if v.type == "BOOL" else str(int(v.range[1]) if v.range else 1)
        lines.append((v.name, val))
    return lines


def _input_sequences(task):
    """Input dicts, in order, drawn from the task's scenario steps (the functional
    probe). Falls back to a single all-inputs-false step if there are no scenarios."""
    seqs = []
    for sc in task.scenarios:
        seq = [dict(step.inputs) for step in sc.steps]
        if seq:
            seqs.append(seq)
    if not seqs:
        seqs = [[{v.name: (False if v.type == "BOOL" else (int(v.range[0]) if v.range else 0))
                  for v in task.interface if v.direction.value == "input"}]]
    return seqs


def _trace(prog, seqs, outnames):
    """Return the concatenated output trace (tuple of tuples) over all input seqs."""
    trace = []
    for seq in seqs:
        st = initial_state(prog)
        for inp in seq:
            for k, v in inp.items():
                st[k] = v
            run_scan(prog, st)
            trace.append(tuple(st.get(o) for o in outnames))
    return tuple(trace)


def _const_trace(outnames, seqs, valfn):
    n = sum(len(s) for s in seqs)
    row = tuple(valfn(o) for o in outnames)
    return tuple(row for _ in range(n))


def analyse_condition(path):
    d = json.load(open(path, encoding="utf-8"))
    per = {"scenario_pass": [], "activates": [], "alloff_equiv": [], "allon_equiv": [],
           "constant": [], "n_samples": 0, "n_parsed": 0}
    for row in d["rows"]:
        lt = _TASKS.get(row["task_id"])
        if lt is None:
            continue
        task = lt.task
        outnames = _output_names(task)
        seqs = _input_sequences(task)
        offvals = dict(_degenerate_body(task, "all-off"))
        onvals = dict(_degenerate_body(task, "all-on"))

        def offval(o):
            v = offvals.get(o, "FALSE")
            return False if v == "FALSE" else (True if v == "TRUE" else int(v))

        def onval(o):
            v = onvals.get(o, "TRUE")
            return False if v == "FALSE" else (True if v == "TRUE" else int(v))

        off_trace = _const_trace(outnames, seqs, offval)
        on_trace = _const_trace(outnames, seqs, onval)
        for s in row.get("samples", []):
            if "error" in s or "code" not in s:
                continue
            per["n_samples"] += 1
            per["scenario_pass"].append(1.0 if s.get("scenario") else 0.0)
            try:
                prog = parse_program(s["code"])
            except (STSyntaxError, Exception):  # noqa: BLE001
                continue
            per["n_parsed"] += 1
            try:
                tr = _trace(prog, seqs, outnames)
            except Exception:  # noqa: BLE001
                continue
            # activation: any output ever TRUE / nonzero across the probe
            activates = any(any(bool(x) for x in step) for step in tr)
            per["activates"].append(1.0 if activates else 0.0)
            per["alloff_equiv"].append(1.0 if tr == off_trace else 0.0)
            per["allon_equiv"].append(1.0 if tr == on_trace else 0.0)
            # constant: same output row every step
            per["constant"].append(1.0 if len(set(tr)) <= 1 else 0.0)
    m = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0
    return {
        "n_samples": per["n_samples"], "n_parsed": per["n_parsed"],
        "scenario_pass_rate": m(per["scenario_pass"]),
        "activation_freq": m(per["activates"]),
        "alloff_equiv_frac": m(per["alloff_equiv"]),
        "allon_equiv_frac": m(per["allon_equiv"]),
        "constant_output_frac": m(per["constant"]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="dir of eval_full <stage>_s<seed>.json")
    ap.add_argument("--stages", default=None, help="comma list; default: all stages found")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    if args.stages:
        stages = args.stages.split(",")
    else:
        stages = sorted({os.path.basename(p).rsplit("_s", 1)[0]
                         for p in glob.glob(os.path.join(args.dir, "*_s*.json"))})
    result = {}
    for stage in stages:
        agg = defaultdict(list)
        for s in seeds:
            p = os.path.join(args.dir, f"{stage}_s{s}.json")
            if not os.path.exists(p):
                continue
            a = analyse_condition(p)
            for k, v in a.items():
                agg[k].append(v)
        if not agg:
            continue
        result[stage] = {k: round(sum(v) / len(v), 4) for k, v in agg.items()}
        r = result[stage]
        print(f"{stage:16s} scen={r['scenario_pass_rate']:.3f} activate={r['activation_freq']:.3f} "
              f"alloff≡={r['alloff_equiv_frac']:.3f} allon≡={r['allon_equiv_frac']:.3f} "
              f"const={r['constant_output_frac']:.3f}")
    out = args.out or os.path.join(args.dir, "output_activity.json")
    json.dump(result, open(out, "w", encoding="utf-8"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
