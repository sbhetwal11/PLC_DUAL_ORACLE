"""Three-way sampled differential validation of the ST semantics (round-12 items 1,2,3,12).

For each in-subset ST program and each of several input traces, the SAME trace is
executed by:
  (a) the scan-cycle interpreter (plcbench.st.interp),
  (b) MATIEC-emitted C compiled with gcc (per-program generated driver; the IEC
      wall clock __CURRENT_TIME advances 1 s per scan), and
  (c) the generated SMV model (plcbench.st.smv) with its free input variables
      constrained to the trace via a step counter, nuXmv proving an INVARSPEC that
      pins every compared variable to the interpreter's value at every step.
All declared BOOL/INT outputs/internals and every TON's Q are compared per scan.

Traces per program: 3 randomized (seeded per program id, recorded) + 4 targeted
boundary traces (all-inputs-held to force timer expiration/saturation; alternating
toggle to force timer resets and edge paths; TRUE/INT=5 held 20 scans then FALSE/0
held 20 scans to force rise->expire->reset for input-monotone timers; and its
complement), 40 scans each.

Timer semantics: the tick abstraction asserts Q on the P-th continuous-IN scan
(rising scan counts as one elapsed dt); MATIEC's wall-clock TON cannot assert Q on
the rising scan under any preset, so agreement with C is checked (i) RAW on the
identical literal source (expected: timer programs show the one-scan-later Q in C)
and (ii) COMP with each `PT := T#Ns` literal rewritten to T#(N-1)s in the source
given to MATIEC only (expected: exact for all presets >= 2 ticks; 1-tick presets
are the boundary case with no wall-clock equivalent). The SMV leg needs no mapping:
the translation and interpreter share the tick semantics by construction, and the
trace check proves it program-by-program.

Case-insensitive identifiers (IEC): programs whose identifier uses differ from the
declaration only by case are case-normalized for the interpreter/translator while
MATIEC compiles the ORIGINAL source (MATIEC resolves case-insensitively itself);
truly undeclared identifiers are rejected and counted separately.

Coverage (per program, over its 7 traces): IF-branch coverage (incl. implicit
else), CASE-label coverage (incl. else), timer rise/expire/reset events, and INT
value spans, measured by an instrumented shadow interpreter.

Run under WSL:  wsl bash toolchain/wsl_analysis.sh analysis/difftest_translator.py
"""
from __future__ import annotations
import glob
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.st.parser import (Assign, Binary, Case, If, Lit, Program, TimerCall,
                                Unary, Var, parse_program, STSyntaxError)
from plcbench.st import interp
from plcbench.st import smv as smvmod
from plcbench.loader import load_all

N_RANDOM = 300
N_MODEL = 200
N_SCANS = 40
N_RAND_TRACES = 3
MATIEC = os.environ.get("MATIEC_IEC2C", os.path.expanduser("~/matiec/iec2c"))
MATIEC_LIB = os.path.join(os.path.dirname(MATIEC), "lib")
MATIEC_C = os.path.join(MATIEC_LIB, "C")
NUXMV = os.environ.get("NUXMV_BIN", "nuXmv")
OUTDIR = "results/difftest_v4"

PT_RE = re.compile(r"(PT\s*:=\s*)T#(\d+)s", re.IGNORECASE)
T1S_RE = re.compile(r"T#1s", re.IGNORECASE)

# populated by pool_model(): originating task id + range-fallback flag per pid
PID_TASK: dict = {}
MODEL_FALLBACK: set = set()


# ------------------------------------------------------------- identifier case
def case_normalize(prog: Program):
    """Rewrite identifier uses whose case differs from the (unique) declaration.
    Returns (n_case_fixes,) and mutates the AST in place. Raises STSyntaxError on
    truly undeclared identifiers or ambiguous case-insensitive collisions."""
    byupper = {}
    for d in prog.decls:
        u = d.name.upper()
        if u in byupper:
            raise STSyntaxError(f"case-insensitive collision {d.name}")
        byupper[u] = d.name
    if prog.name.upper() in byupper:
        raise STSyntaxError("program name collides with a variable")
    timers = {d.name for d in prog.decls if d.type == "TON"}
    fixes = [0]

    def canon(name, member_ok=True):
        if "." in name and member_ok:
            base, mem = name.split(".", 1)
            cb = canon(base, member_ok=False)
            m = mem.upper()
            if m not in ("Q", "ET"):
                raise STSyntaxError(f"unknown member {name!r}")
            return f"{cb}.{m}" if mem != m or cb != base else name
        u = name.upper()
        if u not in byupper:
            raise STSyntaxError(f"undeclared identifier {name!r}")
        c = byupper[u]
        if c != name:
            fixes[0] += 1
        return c

    def walk_expr(e):
        if isinstance(e, Var):
            e.name = canon(e.name)
        elif isinstance(e, Unary):
            walk_expr(e.operand)
        elif isinstance(e, Binary):
            walk_expr(e.left); walk_expr(e.right)

    def walk(stmts):
        for s in stmts:
            if isinstance(s, Assign):
                s.target = canon(s.target); walk_expr(s.expr)
            elif isinstance(s, TimerCall):
                s.instance = canon(s.instance)
                if s.instance not in timers:
                    raise STSyntaxError(f"{s.instance!r} is not a TON instance")
                walk_expr(s.in_expr); walk_expr(s.pt)
            elif isinstance(s, If):
                for cond, body in s.branches:
                    walk_expr(cond); walk(body)
                walk(s.orelse)
            elif isinstance(s, Case):
                walk_expr(s.selector)
                for _, body in s.branches:
                    walk(body)
                walk(s.orelse)

    walk(prog.body)
    return fixes[0]


def prog_info(src):
    prog = parse_program(src)
    n_fixes = case_normalize(prog)
    inputs, compare, timers = [], [], []
    for d in prog.decls:
        if d.type == "TON":
            timers.append(d.name)
        elif d.const:
            continue          # constants are inlined by the translator; not compared
        elif d.direction == "input":
            inputs.append(d)
        else:
            compare.append(d)
    return prog, inputs, compare, timers, n_fixes


# ------------------------------------------------------------------- traces
def make_traces(inputs, seed):
    rng = random.Random(seed)
    traces = []
    for _ in range(N_RAND_TRACES):
        cur = {d.name: (rng.random() < 0.5 if d.type == "BOOL" else rng.randint(0, 5))
               for d in inputs}
        tr = []
        for _ in range(N_SCANS):
            for d in inputs:
                if d.type == "BOOL":
                    if rng.random() < 0.35:
                        cur[d.name] = not cur[d.name]
                elif rng.random() < 0.4:
                    cur[d.name] = rng.randint(0, 5)
            tr.append(dict(cur))
        traces.append(tr)
    # boundary trace 1: everything held (TRUE / max) -> timer expiration+saturation
    traces.append([{d.name: (True if d.type == "BOOL" else 5) for d in inputs}] * N_SCANS)
    # boundary trace 2: global toggle every scan -> rising edges, resets, edge paths
    tr = []
    for k in range(N_SCANS):
        tr.append({d.name: (k % 2 == 0 if d.type == "BOOL" else (k % 6))
                   for d in inputs})
    traces.append(tr)
    # targeted trace 3: all-BOOL TRUE / INT=5 held for 20 scans, then all FALSE / 0
    # held for 20 scans -> forces rise -> expire -> reset for input-monotone timers.
    half = N_SCANS // 2
    hi = {d.name: (True if d.type == "BOOL" else 5) for d in inputs}
    lo = {d.name: (False if d.type == "BOOL" else 0) for d in inputs}
    traces.append([dict(hi) for _ in range(half)] + [dict(lo) for _ in range(N_SCANS - half)])
    # targeted trace 4: the complement (FALSE/0 held then TRUE/5 held).
    traces.append([dict(lo) for _ in range(half)] + [dict(hi) for _ in range(N_SCANS - half)])
    return traces


# ------------------------------------------------- instrumented shadow interp
class Cov:
    def __init__(self, prog, timers):
        self.if_total = self.case_total = 0
        self.if_hit, self.case_hit = set(), set()
        self._index(prog.body)
        self.timer_ev = {t: set() for t in timers}   # rise / expire / reset
        self.int_span = {}

    def _index(self, stmts):
        for s in stmts:
            if isinstance(s, If):
                self.if_total += len(s.branches) + 1      # + implicit/explicit else
                for _, b in s.branches:
                    self._index(b)
                self._index(s.orelse)
            elif isinstance(s, Case):
                self.case_total += len(s.branches) + 1
                for _, b in s.branches:
                    self._index(b)
                self._index(s.orelse)


def run_scan_cov(prog, st, cov: Cov):
    def ev(node):
        return interp._eval(node, st)

    def ex(stmts):
        for s in stmts:
            if isinstance(s, Assign):
                v = ev(s.expr)
                st[s.target] = v
                if isinstance(v, int) and not isinstance(v, bool):
                    lo, hi = cov.int_span.get(s.target, (v, v))
                    cov.int_span[s.target] = (min(lo, v), max(hi, v))
            elif isinstance(s, If):
                done = False
                for bi, (cond, body) in enumerate(s.branches):
                    if ev(cond):
                        cov.if_hit.add((id(s), bi)); ex(body); done = True
                        break
                if not done:
                    cov.if_hit.add((id(s), -1)); ex(s.orelse)
            elif isinstance(s, Case):
                val = ev(s.selector)
                matched = False
                for bi, (labels, body) in enumerate(s.branches):
                    if val in labels:
                        cov.case_hit.add((id(s), bi)); ex(body); matched = True
                        break
                if not matched:
                    cov.case_hit.add((id(s), -1)); ex(s.orelse)
            elif isinstance(s, TimerCall):
                inv = bool(ev(s.in_expr)); pt = ev(s.pt)
                key = f"{s.instance}.ET"
                et0 = st.get(key, 0)
                et = min(et0 + 1, pt) if inv else 0
                st[key] = et
                q0 = st.get(f"{s.instance}.Q", False)
                q = inv and et >= pt
                st[f"{s.instance}.Q"] = q
                if inv and et0 == 0:
                    cov.timer_ev[s.instance].add("rise")
                if q and not q0:
                    cov.timer_ev[s.instance].add("expire")
                if not inv and et0 > 0:
                    cov.timer_ev[s.instance].add("reset")
    ex(prog.body)
    return st


def interp_trace(prog, inputs, compare, timers, trace, cov=None):
    st = interp.initial_state(prog)
    out = []
    for step in trace:
        for name, val in step.items():
            st[name] = val
        if cov is not None:
            run_scan_cov(prog, st, cov)
        else:
            interp.run_scan(prog, st)
        out.append([int(st[d.name]) for d in compare] +
                   [int(st[f"{t}.Q"]) for t in timers])
    return out


# --------------------------------------------------------------- C execution
DRIVER_TMPL = """#include "iec_std_lib.h"
TIME __CURRENT_TIME;
#include "POUS.h"
#include "POUS.c"
#include <stdio.h>

int main(void) {{
  /* static => zero-initialized: MATIEC's __INIT_VAR sets .value but not .flags,
     and a garbage __IEC_FORCE_FLAG bit silently blocks __SET_VAR writes. */
  static {P} inst;
  {P}_init__(&inst, 0);
  long scan = 0;
  int v[{NI}];
  for (;;) {{
    int i, ok = 1;
    for (i = 0; i < {NI}; i++) if (scanf("%d", &v[i]) != 1) {{ ok = 0; break; }}
    if (!ok) break;
    ++scan;
    __CURRENT_TIME.tv_sec = scan; __CURRENT_TIME.tv_nsec = 0;
{SETS}
    {P}_body__(&inst);
{PRINTS}
    printf("\\n");
  }}
  return 0;
}}
"""


def build_driver(prog, inputs, compare, timers):
    P = prog.name.upper()
    sets, prints = [], []
    for i, d in enumerate(inputs):
        ctyp = "BOOL" if d.type == "BOOL" else "INT"
        sets.append(f"    __SET_VAR(inst., {d.name.upper()},, ({ctyp})v[{i}]);")
    for d in compare:
        prints.append(f'    printf("%d ", (int)__GET_VAR(inst.{d.name.upper()},));')
    for t in timers:
        prints.append(f'    printf("%d ", (int)__GET_VAR(inst.{t.upper()}.Q,));')
    return DRIVER_TMPL.format(P=P, NI=max(len(inputs), 1), SETS="\n".join(sets),
                              PRINTS="\n".join(prints))


def c_compile(src, prog, inputs, compare, timers, workdir):
    stpath = os.path.join(workdir, "prog.st")
    with open(stpath, "w") as f:
        f.write(src)
    r = subprocess.run([MATIEC, "-I", MATIEC_LIB, "-T", workdir, stpath],
                       capture_output=True, text=True, timeout=30, cwd=workdir)
    if r.returncode != 0:
        return "iec2c_reject", (r.stderr or r.stdout)[-300:]
    with open(os.path.join(workdir, "driver.c"), "w") as f:
        f.write(build_driver(prog, inputs, compare, timers))
    r = subprocess.run(["gcc", "-I", MATIEC_C, "-o", "driver", "driver.c"],
                       capture_output=True, text=True, timeout=60, cwd=workdir)
    if r.returncode != 0:
        return "gcc_fail", (r.stderr or "")[-300:]
    return "ok", None


def c_run(inputs, trace, workdir):
    stdin = "\n".join(" ".join(str(int(step[d.name])) for d in inputs) or "0"
                      for step in trace)
    r = subprocess.run(["./driver"], input=stdin, capture_output=True,
                       text=True, timeout=30, cwd=workdir)
    if r.returncode != 0:
        return None
    return [[int(x) for x in line.split()] for line in r.stdout.strip().splitlines()]


# --------------------------------------------------------------- SMV leg
def smv_trace_check(prog, ranges, inputs, compare, timers, trace, itr, workdir):
    """Constrain the generated SMV model's inputs to `trace` via a step counter
    and prove (INVARSPEC) that every compared variable equals the interpreter's
    value at every step. Returns 'ok' | 'mismatch' | 'translate_error'."""
    stub = SimpleNamespace(interface=[SimpleNamespace(name=n, range=r)
                                      for n, r in ranges.items()])
    try:
        model = smvmod.model_smv(prog, stub)
    except smvmod.SMVTranslateError as e:
        return "translate_error", str(e)[:200]
    N = len(trace)
    lines = model.splitlines()
    # remove free-input VAR declarations; re-add as trace-driven DEFINEs
    innames = {d.name for d in inputs}
    kept = [ln for ln in lines
            if not any(ln.strip().startswith(f"{n} :") for n in innames)]
    out = list(kept)
    out.append("VAR __step : 0..%d;" % N)
    out.append("ASSIGN init(__step) := 0;")
    out.append("next(__step) := case __step < %d : __step + 1; TRUE : %d; esac;" % (N, N))
    out.append("DEFINE")
    for d in inputs:
        cases = []
        for k, step in enumerate(trace):
            v = step[d.name]
            sv = ("TRUE" if v else "FALSE") if d.type == "BOOL" else str(int(v))
            cases.append(f"__step = {k} : {sv};")
        last = trace[-1][d.name]
        lv = ("TRUE" if last else "FALSE") if d.type == "BOOL" else str(int(last))
        out.append(f"  {d.name} := case " + " ".join(cases) + f" TRUE : {lv}; esac;")
    # expected-trace obligation: state at __step=k carries end-of-scan values of scan k+1
    conj = []
    names = [d.name for d in compare] + [f"{t}__Q" for t in timers]
    types = [d.type for d in compare] + ["BOOL"] * len(timers)
    for k, row in enumerate(itr):
        terms = []
        for (nm, ty, val) in zip(names, types, row):
            if ty == "BOOL":
                terms.append(nm if val else f"!{nm}")
            else:
                terms.append(f"{nm} = {val}")
        conj.append(f"(__step = {k} -> ({' & '.join(terms)}))")
    out.append("INVARSPEC " + " & ".join(conj) + ";")
    path = os.path.join(workdir, "trace.smv")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    r = subprocess.run([NUXMV, path], capture_output=True, text=True, timeout=60,
                       cwd=workdir)
    txt = r.stdout
    if "is true" in txt:
        return "ok", None
    if "is false" in txt:
        return "mismatch", txt[-400:]
    return "translate_error", (r.stderr or txt)[-300:]


# --------------------------------------------------------------- comparison
def compare_traces(a, b):
    return sum(1 for ra, rb in zip(a, b) for va, vb in zip(ra, rb) if va != vb)


def run_program(pid, src, ranges):
    seed = int(hashlib.sha1(pid.encode()).hexdigest()[:8], 16)
    res = {"id": pid, "seed": seed}
    try:
        prog, inputs, compare, timers, n_fixes = prog_info(src)
    except STSyntaxError as e:
        msg = str(e)
        kind = ("undeclared" if "undeclared" in msg else
                "collision" if "collision" in msg or "collides" in msg else "parse")
        return {"id": pid, "status": f"reject_{kind}", "detail": msg[:200]}
    if not compare and not timers:
        return {"id": pid, "status": "nothing_to_compare"}
    res.update({"status": "ok", "case_fixes": n_fixes, "has_timer": bool(timers)})
    pts = [int(m.group(2)) for m in PT_RE.finditer(src)]
    res["has_pt1"] = any(n <= 1 for n in pts)
    res["has_t1s"] = bool(T1S_RE.search(src))
    traces = make_traces(inputs, seed)
    cov = Cov(prog, timers)
    itrs = []
    try:
        for tr in traces:
            itrs.append(interp_trace(prog, inputs, compare, timers, tr, cov=cov))
    except Exception as e:
        return {"id": pid, "status": "interp_runtime_error", "detail": str(e)[:200]}
    res["coverage"] = {
        "if_branches": [len(cov.if_hit), cov.if_total],
        "case_labels": [len(cov.case_hit), cov.case_total],
        "timer_events": {t: sorted(v) for t, v in cov.timer_ev.items()},
        "int_span": {k: list(v) for k, v in cov.int_span.items()},
        "n_traces": len(traces), "n_scans": N_SCANS,
    }

    with tempfile.TemporaryDirectory(prefix="difftest_") as wd:
        st, detail = c_compile(src, prog, inputs, compare, timers, wd)
        if st != "ok":
            res.update({"status": st, "detail": detail}); return res
        res["raw_mm"] = 0
        for tr, itr in zip(traces, itrs):
            ct = c_run(inputs, tr, wd)
            if ct is None:
                res.update({"status": "run_fail"}); return res
            res["raw_mm"] += compare_traces(itr, ct)

    if timers:
        comp_src, nsub = PT_RE.subn(
            lambda m: f"{m.group(1)}T#{max(int(m.group(2)) - 1, 0)}s", src)
        if nsub == 0:
            res["comp"] = "no_rewritable_pt"
        else:
            with tempfile.TemporaryDirectory(prefix="difftest_") as wd:
                st, detail = c_compile(comp_src, prog, inputs, compare, timers, wd)
                if st != "ok":
                    res["comp"] = st
                else:
                    mm = 0
                    for tr, itr in zip(traces, itrs):
                        ct = c_run(inputs, tr, wd)
                        if ct is None:
                            mm = -1; break
                        mm += compare_traces(itr, ct)
                    res["comp"] = "run_fail" if mm < 0 else "ok"
                    res["comp_mm"] = max(mm, 0)

    if ranges is not None:
        res["smv"] = "ok"; res["smv_mm_traces"] = 0
        with tempfile.TemporaryDirectory(prefix="difftest_smv_") as wd:
            for tr, itr in zip(traces, itrs):
                st, detail = smv_trace_check(prog, ranges, inputs, compare, timers,
                                             tr, itr, wd)
                if st == "mismatch":
                    res["smv"] = "mismatch"; res["smv_mm_traces"] += 1
                    res["smv_detail"] = detail
                elif st != "ok":
                    res["smv"] = st; res["smv_detail"] = detail
                    break
    else:
        res["smv"] = "skipped_no_ranges"
    return res


# --------------------------------------------------------------- pools
def pool_refs():
    by_id = {}
    for lt in load_all():
        by_id[lt.task.id] = lt
    out = []
    for tid in sorted(by_id):
        lt = by_id[tid]
        ranges = {v.name: tuple(v.range) for v in lt.task.interface if v.range}
        out.append((f"ref:{tid}", lt.reference_st, ranges))
    return out


def pool_random():
    from analysis._difftest_gen import Gen
    out = []
    for s in range(N_RANDOM):
        g = Gen(s)
        src = g.program()
        prog = parse_program(src)
        ranges = {}
        for d in prog.decls:
            if d.type == "INT":
                ranges[d.name] = (0, 5) if d.direction == "input" else (0, 6)
        out.append((f"rand:{s}", src, ranges))
    return out


def pool_model():
    # task table for interface ranges (same source as pool_refs)
    tasks = {lt.task.id: lt.task for lt in load_all()}
    seen, out = set(), []
    codes = []  # (code, originating_task_id)
    for f in sorted(glob.glob("results/exp1a/*_s*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for row in d["rows"]:
            tid = row.get("task_id")           # keep the originating task_id
            for s in row["samples"]:
                code = (s.get("code") or "").strip()
                if not code:
                    continue
                h = hashlib.sha1(code.encode()).hexdigest()
                if h in seen:
                    continue
                seen.add(h)
                codes.append((code, tid))
    random.Random(0).shuffle(codes)
    kept = 0
    for code, tid in codes:
        if kept >= N_MODEL:
            break
        try:
            prog = parse_program(code)
        except Exception:
            continue
        pid = f"model:{hashlib.sha1(code.encode()).hexdigest()[:10]}"
        task = tasks.get(tid)
        # ranges from the originating task interface (like pool_refs) so the SMV
        # leg can run for model programs too.
        ranges = {}
        if task is not None:
            ranges = {v.name: tuple(v.range) for v in task.interface if v.range}
        # fallback (0,100) ONLY for internal/output INTs absent from the interface.
        fallback = False
        for dcl in prog.decls:
            if (dcl.type == "INT" and dcl.name not in ranges
                    and dcl.direction in ("internal", "output")):
                ranges[dcl.name] = (0, 100)
                fallback = True
        PID_TASK[pid] = tid
        if fallback:
            MODEL_FALLBACK.add(pid)
        out.append((pid, code, ranges))
        kept += 1
    return out


# --------------------------------------------------------------- main
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    pools = [("refs", pool_refs()), ("random", pool_random()),
             ("model", pool_model())]
    summary, per_program = {}, {}
    for pname, progs in pools:
        agg = {"n": len(progs), "timer_progs": 0, "timerless": 0,
               "raw_exact": 0, "raw_mismatch_timerless": 0, "raw_mismatch_timer": 0,
               "comp_exact": 0, "comp_mismatch_pt1": 0, "comp_mismatch_no_pt1": 0,
               "comp_na": 0, "smv_ok": 0, "smv_mismatch": 0, "smv_translate_error": 0,
               "smv_skipped": 0, "case_normalized_progs": 0,
               "reject_undeclared": 0, "reject_collision": 0, "reject_other": 0,
               "toolchain_reject": 0, "model_range_fallback": 0}
        rows = []
        for i, (pid, src, ranges) in enumerate(progs):
            r = run_program(pid, src, ranges)
            if pname == "model":
                r["task_id"] = PID_TASK.get(pid)
                r["range_fallback"] = pid in MODEL_FALLBACK
                if r["range_fallback"]:
                    agg["model_range_fallback"] += 1
            rows.append(r)
            st = r["status"]
            if st.startswith("reject_"):
                agg["toolchain_reject"] += 1
                agg["reject_undeclared" if st == "reject_undeclared" else
                    "reject_collision" if st == "reject_collision" else
                    "reject_other"] += 1
                continue
            if st in ("iec2c_reject", "gcc_fail", "run_fail", "nothing_to_compare",
                      "interp_runtime_error"):
                agg["toolchain_reject"] += 1
                agg["reject_other"] += 1
                continue
            if r.get("case_fixes"):
                agg["case_normalized_progs"] += 1
            if r["has_timer"]:
                agg["timer_progs"] += 1
                if r["raw_mm"] == 0:
                    agg["raw_exact"] += 1
                else:
                    agg["raw_mismatch_timer"] += 1
                comp = r.get("comp")
                if comp == "ok":
                    if r.get("comp_mm", 0) == 0:
                        agg["comp_exact"] += 1
                    elif r.get("has_pt1"):
                        agg["comp_mismatch_pt1"] += 1
                    else:
                        agg["comp_mismatch_no_pt1"] += 1
                else:
                    agg["comp_na"] += 1
            else:
                agg["timerless"] += 1
                if r["raw_mm"] == 0:
                    agg["raw_exact"] += 1
                else:
                    agg["raw_mismatch_timerless"] += 1
            smv = r.get("smv")
            if smv == "ok":
                agg["smv_ok"] += 1
            elif smv == "mismatch":
                agg["smv_mismatch"] += 1
            elif smv == "translate_error":
                agg["smv_translate_error"] += 1
            else:
                agg["smv_skipped"] += 1
            if (i + 1) % 50 == 0:
                print(f"  {pname}: {i + 1}/{len(progs)}", flush=True)
        summary[pname] = agg
        per_program[pname] = rows
        print(f"== {pname}: {agg}", flush=True)

    # aggregate coverage over comparable programs
    covagg = {"if": [0, 0], "case": [0, 0], "timers_all3": 0, "timers_total": 0,
              "timers_never_rose": 0, "timers_rose_never_expired": 0,
              "timers_expired_never_reset": 0,
              # same breakdown restricted to timers in programs containing T#1s
              "t1s_timers_total": 0, "t1s_timers_all3": 0, "t1s_timers_never_rose": 0,
              "t1s_timers_rose_never_expired": 0, "t1s_timers_expired_never_reset": 0}
    all3 = {"rise", "expire", "reset"}
    for pname in per_program:
        for r in per_program[pname]:
            c = r.get("coverage")
            if not c or r["status"] != "ok":
                continue
            covagg["if"][0] += c["if_branches"][0]; covagg["if"][1] += c["if_branches"][1]
            covagg["case"][0] += c["case_labels"][0]; covagg["case"][1] += c["case_labels"][1]
            is_t1s = bool(r.get("has_t1s"))
            for t, ev in c["timer_events"].items():
                evs = set(ev)
                rose = "rise" in evs
                expired = "expire" in evs
                did_reset = "reset" in evs
                covagg["timers_total"] += 1
                if not rose:
                    covagg["timers_never_rose"] += 1
                if rose and not expired:
                    covagg["timers_rose_never_expired"] += 1
                if expired and not did_reset:
                    covagg["timers_expired_never_reset"] += 1
                if all3 <= evs:
                    covagg["timers_all3"] += 1
                if is_t1s:
                    covagg["t1s_timers_total"] += 1
                    if not rose:
                        covagg["t1s_timers_never_rose"] += 1
                    if rose and not expired:
                        covagg["t1s_timers_rose_never_expired"] += 1
                    if expired and not did_reset:
                        covagg["t1s_timers_expired_never_reset"] += 1
                    if all3 <= evs:
                        covagg["t1s_timers_all3"] += 1
    print("== coverage:", covagg, flush=True)

    doc = {"n_scans": N_SCANS, "n_rand_traces": N_RAND_TRACES,
           "traces_per_program": N_RAND_TRACES + 4,
           "seed_rule": "sha1(program_id)[:8] as int, recorded per program",
           "summary": summary, "coverage_aggregate": covagg,
           "per_program": per_program}
    with open(os.path.join(OUTDIR, "difftest_summary.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("wrote", os.path.join(OUTDIR, "difftest_summary.json"))


if __name__ == "__main__":
    main()
