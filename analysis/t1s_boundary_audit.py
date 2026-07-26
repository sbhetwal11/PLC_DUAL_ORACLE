"""C2: T#1s timer first-assertion boundary-dependence audit (analysis-only).

Question: does any REPORTED verdict depend on the timer first-assertion boundary?
  standard (tick) semantics: TON.Q asserts on the PT-th continuous-IN scan.
  variant  (wall-clock/delayed) semantics: Q asserts on the (PT+1)-th scan.

We build a VARIANT scorer that mirrors the harness pipeline but with delayed-Q,
WITHOUT touching plcbench:
  * scenario dimension: a local copy of the interpreter timer update where
    q = inv and (et_prev >= pt) is evaluated BEFORE incrementing ET.
  * invariant dimension: a copy of plcbench.st.smv.{symexec,model_smv} where the
    ONLY change is the timer Q DEFINE: q = IN & (ET_prev >= pt) (uses the stored
    previous-scan counter instead of the current-scan ET).

Both variants are unit-tested on a trivial TON (PT=2, IN held): variant Q must
first assert at scan 3, standard at scan 2.

Then we re-score ONLY samples whose code contains T#1s (case-insensitive) across
results/exp1a/*_s*.json, results/exp1b/*_s*.json, results/frontier_n10/*.json,
results/frontier_n10_constrained/*.json, plus the H01 reference itself. For each
dataset we report: #samples with T#1s, #invariant-verdict changes, #scenario
changes, #task-valid changes.

A "change" is counted only when BOTH legs give a CLEAN verdict (pass/fail) and
they differ, isolating the boundary effect. Published numbers are untouched.

Run:  wsl bash toolchain/wsl_analysis.sh analysis/t1s_boundary_audit.py
"""
from __future__ import annotations
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.st.parser import (Assign, Binary, Case, If, Lit, Program, TimerCall,
                                Unary, Var, parse_program, STSyntaxError)
from plcbench.st import interp
from plcbench.st import smv as smvmod
from plcbench.st.smv import (expr_to_smv, _build_case, _collect_assigned, _const_int,
                             _lit, _smv_type, spec_line, SMVTranslateError)
from plcbench.loader import load_all

NUXMV = os.environ.get("NUXMV_BIN", "nuXmv")
OUTDIR = "results"
OUTFILE = os.path.join(OUTDIR, "t1s_boundary_audit.json")
T1S = re.compile(r"t#1s", re.IGNORECASE)
NUXMV_TIMEOUT = 90
NWORKERS = 12


# =========================================================================
#  VARIANT INTERPRETER  (delayed-Q scenario semantics)
# =========================================================================
def _exec_var(stmts, st: dict):
    """Copy of interp._exec with delayed-Q timer semantics (Q uses ET BEFORE
    incrementing -> first asserts on the (PT+1)-th continuous-IN scan)."""
    for s in stmts:
        if isinstance(s, Assign):
            st[s.target] = interp._eval(s.expr, st)
        elif isinstance(s, If):
            done = False
            for cond, body in s.branches:
                if interp._eval(cond, st):
                    _exec_var(body, st)
                    done = True
                    break
            if not done:
                _exec_var(s.orelse, st)
        elif isinstance(s, Case):
            val = interp._eval(s.selector, st)
            matched = False
            for labels, body in s.branches:
                if val in labels:
                    _exec_var(body, st)
                    matched = True
                    break
            if not matched:
                _exec_var(s.orelse, st)
        elif isinstance(s, TimerCall):
            inv = bool(interp._eval(s.in_expr, st))
            pt = interp._eval(s.pt, st)
            et_prev = st.get(f"{s.instance}.ET", 0)
            q = inv and (et_prev >= pt)                    # BEFORE increment
            et = min(et_prev + 1, pt) if inv else 0
            st[f"{s.instance}.ET"] = et
            st[f"{s.instance}.Q"] = q
        else:
            raise TypeError(f"cannot execute statement {s!r}")


def run_scan_var(prog: Program, st: dict) -> dict:
    _exec_var(prog.body, st)
    return st


def check_scenarios_var(prog: Program, scenarios: list) -> list:
    """Copy of interp.check_scenarios using the variant scan."""
    results = []
    for sc in scenarios:
        st = interp.initial_state(prog)
        ok, detail = True, ""
        for k, step in enumerate(sc.steps):
            for name, val in step.inputs.items():
                st[name] = val
            run_scan_var(prog, st)
            for name, exp in step.expect.items():
                if st.get(name) != exp:
                    ok = False
                    detail = f"step {k}: {name}={st.get(name)} expected {exp}"
                    break
            if not ok:
                break
        results.append((sc.id, ok, detail))
    return results


# =========================================================================
#  VARIANT SMV TRANSLATOR  (delayed-Q invariant semantics)
#  Copies smv.symexec + smv.model_smv; the ONLY change is the timer Q DEFINE.
# =========================================================================
def symexec_var(stmts, env: dict, ctx: dict, top_level: bool = True) -> None:
    for s in stmts:
        if isinstance(s, Assign):
            env[s.target] = expr_to_smv(s.expr, env)

        elif isinstance(s, TimerCall):
            if not top_level:
                raise SMVTranslateError(
                    "TON calls must be at the program-body top level (gate via IN)")
            in_smv = expr_to_smv(s.in_expr, env)
            pt = _const_int(s.pt, ctx["consts"])
            inst = s.instance
            etp = f"{inst}__ET__prev"
            et_expr = f"case !({in_smv}) : 0; {etp} < {pt} : {etp} + 1; TRUE : {pt}; esac"
            # ---- ONLY CHANGE vs plcbench.st.smv: Q uses ET_prev, not current ET ----
            q_expr = f"(({in_smv}) & ({inst}__ET__prev >= {pt}))"
            # ------------------------------------------------------------------------
            ctx["timers"][inst] = {"pt": pt, "et": et_expr, "q": q_expr}
            env[f"{inst}.ET"] = f"{inst}__ET"
            env[f"{inst}.Q"] = f"{inst}__Q"

        elif isinstance(s, If):
            pre = dict(env)
            assigned: set = set()
            _collect_assigned([s], assigned)
            branch_results = []
            for cond, body in s.branches:
                cond_smv = expr_to_smv(cond, pre)
                benv = dict(pre)
                symexec_var(body, benv, ctx, top_level=False)
                branch_results.append((cond_smv, benv))
            else_env = dict(pre)
            symexec_var(s.orelse, else_env, ctx, top_level=False)
            for v in assigned:
                cases = [(c, benv.get(v, pre.get(v, v))) for c, benv in branch_results]
                env[v] = _build_case(cases, else_env.get(v, pre.get(v, v)))

        elif isinstance(s, Case):
            pre = dict(env)
            assigned = set()
            _collect_assigned([s], assigned)
            sel = expr_to_smv(s.selector, pre)
            branch_results = []
            for labels, body in s.branches:
                cond = " | ".join(f"({sel} = {lab})" for lab in sorted(labels))
                benv = dict(pre)
                symexec_var(body, benv, ctx, top_level=False)
                branch_results.append((cond, benv))
            else_env = dict(pre)
            symexec_var(s.orelse, else_env, ctx, top_level=False)
            for v in assigned:
                cases = [(c, benv.get(v, pre.get(v, v))) for c, benv in branch_results]
                env[v] = _build_case(cases, else_env.get(v, pre.get(v, v)))
        else:
            raise SMVTranslateError(f"cannot translate statement {s!r}")


def model_smv_var(prog: Program, task) -> str:
    """Copy of smv.model_smv but calling symexec_var (delayed-Q). Pre-seed of
    read-before-call Q is left unchanged per the audit spec (only the Q DEFINE
    changes)."""
    ranges = {v.name: v.range for v in task.interface if v.range}
    decls = prog.decls
    consts = {d.name: d.init for d in decls if d.const}
    inputs = [d for d in decls if d.direction == "input" and not d.const and d.type != "TON"]
    states = [d for d in decls if d.direction in ("output", "internal")
              and not d.const and d.type != "TON"]
    timer_decls = [d for d in decls if d.type == "TON"]

    env = {}
    for d in inputs:
        env[d.name] = d.name
    for d in states:
        env[d.name] = f"{d.name}__prev"
    for d in consts:
        env[d] = _lit(consts[d])
    prescanned_pt = {}
    for s in prog.body:
        if isinstance(s, TimerCall):
            try:
                prescanned_pt[s.instance] = _const_int(s.pt, consts)
            except SMVTranslateError:
                pass
    for d in timer_decls:
        env[f"{d.name}.ET"] = f"{d.name}__ET__prev"
        pt0 = prescanned_pt.get(d.name)
        env[f"{d.name}.Q"] = (f"({d.name}__ET__prev >= {pt0})"
                              if pt0 and pt0 >= 1 else "FALSE")

    ctx = {"timers": {}, "consts": consts}
    symexec_var(prog.body, env, ctx)
    timers = ctx["timers"]

    lines = ["MODULE main", "VAR"]
    for d in inputs:
        lines.append(f"  {d.name} : {_smv_type(d.name, d.type, ranges)};")
    for d in states:
        lines.append(f"  {d.name}__prev : {_smv_type(d.name, d.type, ranges)};")
    for inst, t in timers.items():
        lines.append(f"  {inst}__ET__prev : 0..{t['pt']};")

    lines.append("DEFINE")
    for d in states:
        lines.append(f"  {d.name} := {env[d.name]};")
    for inst, t in timers.items():
        lines.append(f"  {inst}__ET := {t['et']};")
        lines.append(f"  {inst}__Q := {t['q']};")

    lines.append("ASSIGN")
    for d in states:
        default = _lit(d.init) if d.init is not None else (
            "FALSE" if d.type == "BOOL" else str(int(ranges.get(d.name, [0, 0])[0])))
        lines.append(f"  init({d.name}__prev) := {default};")
        lines.append(f"  next({d.name}__prev) := {d.name};")
    for inst in timers:
        lines.append(f"  init({inst}__ET__prev) := 0;")
        lines.append(f"  next({inst}__ET__prev) := {inst}__ET;")

    return "\n".join(lines) + "\n"


def translate_std(prog, task):
    return smvmod.translate(prog, task)


def translate_var(prog, task):
    out = [model_smv_var(prog, task)]
    for p in task.safety_properties:
        out.append(f"-- {p.id}")
        out.append(spec_line(p))
    return "\n".join(out) + "\n"


# =========================================================================
#  nuXmv runner (all SPECs in one invocation -> one run per leg)
# =========================================================================
_TRUE = re.compile(r"specification .* is true", re.IGNORECASE)
_FALSE = re.compile(r"specification .* is false", re.IGNORECASE)


def run_nuxmv_verdict(smv_text: str, nprops: int):
    """Return 'pass' | 'fail' | 'error'. pass iff all nprops SPECs are true."""
    with tempfile.TemporaryDirectory(prefix="t1saudit_") as td:
        path = os.path.join(td, "m.smv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(smv_text)
        try:
            r = subprocess.run([NUXMV, path], capture_output=True, text=True,
                               errors="replace", timeout=NUXMV_TIMEOUT)
        except subprocess.TimeoutExpired:
            return "error"
    out = r.stdout + "\n" + r.stderr
    ntrue = len(_TRUE.findall(out))
    nfalse = len(_FALSE.findall(out))
    if nfalse > 0:
        return "fail"
    if ntrue == nprops and nprops > 0:
        return "pass"
    return "error"


# =========================================================================
#  per-(task,code) scorer  (worker)
# =========================================================================
def score_unit(args):
    """args = (task_id, code). Returns dict of std/var verdicts for inv + scen."""
    task_id, code = args
    task = TASKS[task_id].task
    res = {"task_id": task_id, "parse_ok": False,
           "inv_std": "error", "inv_var": "error",
           "scen_std": "error", "scen_var": "error"}
    try:
        prog = parse_program(code)
    except Exception:
        return res
    res["parse_ok"] = True

    # ---- invariant dimension (nuXmv) ----
    nprops = len(task.safety_properties)
    try:
        smv_std = translate_std(prog, task)
        smv_var = translate_var(prog, task)
    except (SMVTranslateError, STSyntaxError, Exception):
        smv_std = smv_var = None
    if smv_std is not None:
        res["inv_std"] = run_nuxmv_verdict(smv_std, nprops)
        res["inv_var"] = run_nuxmv_verdict(smv_var, nprops)

    # ---- scenario dimension (interp) ----
    scenarios = task.scenarios
    if scenarios:
        try:
            rs = interp.check_scenarios(prog, scenarios)
            res["scen_std"] = "pass" if all(ok for _, ok, _ in rs) else "fail"
        except Exception:
            res["scen_std"] = "error"
        try:
            rv = check_scenarios_var(prog, scenarios)
            res["scen_var"] = "pass" if all(ok for _, ok, _ in rv) else "fail"
        except Exception:
            res["scen_var"] = "error"
    else:
        res["scen_std"] = res["scen_var"] = "no_scenarios"
    return res


# =========================================================================
#  unit tests (must pass before trusting the audit)
# =========================================================================
TRIVIAL_TON = """PROGRAM ton_test
VAR_INPUT
  Trig : BOOL;
END_VAR
VAR
  T1 : TON;
  Qout : BOOL;
END_VAR
T1(IN := Trig, PT := T#2s);
Qout := T1.Q;
END_PROGRAM
"""


def unit_test_interp():
    prog = parse_program(TRIVIAL_TON)
    # standard
    st = interp.initial_state(prog)
    std_q = []
    for _ in range(5):
        st["Trig"] = True
        interp.run_scan(prog, st)
        std_q.append(int(st["Qout"]))
    # variant
    st = interp.initial_state(prog)
    var_q = []
    for _ in range(5):
        st["Trig"] = True
        run_scan_var(prog, st)
        var_q.append(int(st["Qout"]))
    std_first = std_q.index(1) + 1 if 1 in std_q else None
    var_first = var_q.index(1) + 1 if 1 in var_q else None
    print(f"[unit:interp] PT=2 IN held: std Q seq {std_q} (first@scan {std_first}) "
          f"| var Q seq {var_q} (first@scan {var_first})")
    assert std_first == 2, f"standard interp Q should first assert at scan 2, got {std_first}"
    assert var_first == 3, f"variant interp Q should first assert at scan 3, got {var_first}"
    return std_q, var_q


def _smv_trace_verdict(prog, task_stub, model_fn, expected_q, workdir):
    """Force Trig=TRUE each step and assert Qout matches expected_q per scan.
    Returns True iff nuXmv proves the INVARSPEC (i.e. model's Q == expected_q)."""
    model = model_fn(prog, task_stub)
    N = len(expected_q)
    lines = [ln for ln in model.splitlines()
             if not ln.strip().startswith("Trig :")]
    out = list(lines)
    out.append("VAR __step : 0..%d;" % N)
    out.append("ASSIGN init(__step) := 0;")
    out.append("next(__step) := case __step < %d : __step + 1; TRUE : %d; esac;" % (N, N))
    out.append("DEFINE Trig := TRUE;")
    conj = []
    for k, q in enumerate(expected_q):
        term = "Qout" if q else "!Qout"
        conj.append(f"(__step = {k} -> {term})")
    out.append("INVARSPEC " + " & ".join(conj) + ";")
    path = os.path.join(workdir, "u.smv")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    r = subprocess.run([NUXMV, path], capture_output=True, text=True,
                       errors="replace", timeout=60, cwd=workdir)
    txt = r.stdout + r.stderr
    return "is true" in txt


def unit_test_smv(std_q, var_q):
    prog = parse_program(TRIVIAL_TON)
    stub = SimpleNamespace(interface=[], safety_properties=[])
    with tempfile.TemporaryDirectory(prefix="t1sunit_") as wd:
        # standard model must match std_q, NOT var_q
        s_vs_std = _smv_trace_verdict(prog, stub, smvmod.model_smv, std_q, wd)
        s_vs_var = _smv_trace_verdict(prog, stub, smvmod.model_smv, var_q, wd)
        # variant model must match var_q, NOT std_q
        v_vs_std = _smv_trace_verdict(prog, stub, model_smv_var, std_q, wd)
        v_vs_var = _smv_trace_verdict(prog, stub, model_smv_var, var_q, wd)
    print(f"[unit:smv] std-model==std_q:{s_vs_std} std-model==var_q:{s_vs_var} | "
          f"var-model==std_q:{v_vs_std} var-model==var_q:{v_vs_var}")
    assert s_vs_std and not s_vs_var, "standard SMV model must match tick Q, not delayed Q"
    assert v_vs_var and not v_vs_std, "variant SMV model must match delayed Q, not tick Q"


# =========================================================================
#  dataset collection
# =========================================================================
def dataset_files():
    return {
        "exp1a": [f for f in sorted(glob.glob("results/exp1a/*_s*.json"))
                  if "output_activity" not in f],
        "exp1b": [f for f in sorted(glob.glob("results/exp1b/*_s*.json"))
                  if "output_activity" not in f],
        "frontier_n10": sorted(glob.glob("results/frontier_n10/*.json")),
        "frontier_n10_constrained": sorted(glob.glob("results/frontier_n10_constrained/*.json")),
    }


def collect_samples():
    """Return dataset -> list of sample dicts {task_id, code, compile}; and the
    H01 reference as its own dataset. Also return the unique (task_id, code) set."""
    datasets = {}
    uniq = set()
    valid_task_ids = set(TASKS.keys())
    for ds, files in dataset_files().items():
        samples = []
        for f in files:
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            if "rows" not in d:
                continue
            for row in d["rows"]:
                tid = row["task_id"]
                if tid not in valid_task_ids:
                    continue
                for s in row["samples"]:
                    code = (s.get("code") or "")
                    if not T1S.search(code):
                        continue
                    samples.append({"task_id": tid, "code": code,
                                    "compile": bool(s.get("compile"))})
                    uniq.add((tid, code))
        datasets[ds] = samples
    # H01 reference itself
    h01 = TASKS["H01_intersection_signals"]
    ref_code = h01.reference_st
    datasets["H01_reference"] = [{"task_id": "H01_intersection_signals",
                                  "code": ref_code, "compile": True}]
    uniq.add(("H01_intersection_signals", ref_code))
    return datasets, uniq


def verdict_pass(v):
    return v == "pass"


def clean(v):
    return v in ("pass", "fail")


def tally(samples, cache):
    n = len(samples)
    inv_chg = scen_chg = tv_chg = 0
    inv_indet = scen_indet = 0
    parse_ok = 0
    for s in samples:
        r = cache[(s["task_id"], s["code"])]
        if r["parse_ok"]:
            parse_ok += 1
        # invariant change
        if clean(r["inv_std"]) and clean(r["inv_var"]):
            if r["inv_std"] != r["inv_var"]:
                inv_chg += 1
        else:
            inv_indet += 1
        # scenario change
        ss, sv = r["scen_std"], r["scen_var"]
        if ss in ("pass", "fail") and sv in ("pass", "fail"):
            if ss != sv:
                scen_chg += 1
        elif ss == "no_scenarios":
            pass
        else:
            scen_indet += 1
        # task-valid change (compile & inv & scen); boundary can only flip inv/scen
        comp = s["compile"]
        inv_s_ok = verdict_pass(r["inv_std"])
        inv_v_ok = verdict_pass(r["inv_var"])
        scen_s_ok = (r["scen_std"] in ("pass", "no_scenarios"))
        scen_v_ok = (r["scen_var"] in ("pass", "no_scenarios"))
        # only count when both legs are computable (not error) to avoid spurious flips
        inv_computable = clean(r["inv_std"]) and clean(r["inv_var"])
        scen_computable = (ss in ("pass", "fail", "no_scenarios")
                           and sv in ("pass", "fail", "no_scenarios"))
        if inv_computable and scen_computable:
            tv_std = comp and inv_s_ok and scen_s_ok
            tv_var = comp and inv_v_ok and scen_v_ok
            if tv_std != tv_var:
                tv_chg += 1
    return {"n_samples": n, "parse_ok": parse_ok,
            "invariant_changes": inv_chg, "scenario_changes": scen_chg,
            "taskvalid_changes": tv_chg,
            "invariant_indeterminate": inv_indet, "scenario_indeterminate": scen_indet}


# module-level task table (built in main, before Pool fork)
TASKS = {}


def main():
    global TASKS
    os.makedirs(OUTDIR, exist_ok=True)
    print("Loading tasks ...", flush=True)
    TASKS = {lt.task.id: lt for lt in load_all()}
    print(f"  {len(TASKS)} tasks loaded", flush=True)

    print("\n=== UNIT TESTS (variant semantics) ===", flush=True)
    std_q, var_q = unit_test_interp()
    unit_test_smv(std_q, var_q)
    print("  unit tests PASSED\n", flush=True)

    print("Collecting T#1s samples ...", flush=True)
    datasets, uniq = collect_samples()
    for ds, samples in datasets.items():
        print(f"  {ds}: {len(samples)} T#1s samples", flush=True)
    uniq = sorted(uniq)
    print(f"  {len(uniq)} unique (task,code) units to score with nuXmv", flush=True)

    print(f"\nScoring {len(uniq)} units on {NWORKERS} workers ...", flush=True)
    with Pool(NWORKERS) as pool:
        results = pool.map(score_unit, uniq, chunksize=4)
    cache = {}
    for (tid, code), r in zip(uniq, results):
        cache[(tid, code)] = r
    print("  scoring complete", flush=True)

    per_dataset = {}
    for ds, samples in datasets.items():
        per_dataset[ds] = tally(samples, cache)

    # collect the concrete changed units (for the report / auditability)
    changed_units = []
    for (tid, code), r in cache.items():
        inv_flip = clean(r["inv_std"]) and clean(r["inv_var"]) and r["inv_std"] != r["inv_var"]
        scen_flip = (r["scen_std"] in ("pass", "fail") and r["scen_var"] in ("pass", "fail")
                     and r["scen_std"] != r["scen_var"])
        if inv_flip or scen_flip:
            changed_units.append({"task_id": tid, "code_sha1": hashlib.sha1(code.encode()).hexdigest()[:12],
                                  "inv_std": r["inv_std"], "inv_var": r["inv_var"],
                                  "scen_std": r["scen_std"], "scen_var": r["scen_var"]})

    doc = {"metric": "T#1s boundary-dependence audit (analysis-only variant)",
           "semantics": {"standard": "Q asserts on PT-th continuous-IN scan",
                         "variant": "Q asserts on (PT+1)-th continuous-IN scan (delayed)"},
           "unit_test": {"std_Q_seq_PT2_INheld": std_q, "var_Q_seq_PT2_INheld": var_q},
           "nuxmv_timeout_s": NUXMV_TIMEOUT,
           "n_unique_units": len(uniq),
           "per_dataset": per_dataset,
           "changed_units": changed_units}
    with open(OUTFILE, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)

    print("\n=== C2 RESULTS: T#1s boundary-dependence per dataset ===")
    hdr = f"{'dataset':28s} {'#T#1s':>6} {'parseOK':>7} {'invChg':>7} {'scenChg':>8} {'tvChg':>6} {'invIndet':>9} {'scnIndet':>9}"
    print(hdr)
    print("-" * len(hdr))
    for ds in ["exp1a", "exp1b", "frontier_n10", "frontier_n10_constrained", "H01_reference"]:
        a = per_dataset[ds]
        print(f"{ds:28s} {a['n_samples']:>6} {a['parse_ok']:>7} "
              f"{a['invariant_changes']:>7} {a['scenario_changes']:>8} "
              f"{a['taskvalid_changes']:>6} {a['invariant_indeterminate']:>9} "
              f"{a['scenario_indeterminate']:>9}")
    tot_inv = sum(per_dataset[d]["invariant_changes"] for d in per_dataset)
    tot_scen = sum(per_dataset[d]["scenario_changes"] for d in per_dataset)
    tot_tv = sum(per_dataset[d]["taskvalid_changes"] for d in per_dataset)
    print("-" * len(hdr))
    print(f"TOTAL invariant_changes={tot_inv} scenario_changes={tot_scen} taskvalid_changes={tot_tv}")
    print(f"\n{len(changed_units)} unique units show a boundary-dependent flip")
    for cu in changed_units:
        print("  ", cu)
    print(f"\nsaved {OUTFILE}")


if __name__ == "__main__":
    main()
