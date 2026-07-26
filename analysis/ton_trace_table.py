"""Round-12 item 2: (a) concrete per-scan TON trace tables for T#1s/T#2s/T#3s
across the three systems (MATIEC C with wall-clock internals, interpreter, SMV
recurrence == interpreter by construction and proven by the trace leg), on the
UNCHANGED literal source; (b) check H01's four propositional G-invariants on the
MATIEC-C wall-clock traces (does the one-scan timer shift ever break the verified
safety structure on sampled traces?).

Run: wsl bash toolchain/wsl_analysis.sh analysis/ton_trace_table.py
"""
from __future__ import annotations
import os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.st.parser import parse_program
from plcbench.st import interp

MATIEC = os.environ.get("MATIEC_IEC2C", os.path.expanduser("~/matiec/iec2c"))
MATIEC_LIB = os.path.join(os.path.dirname(MATIEC), "lib")
MATIEC_C = os.path.join(MATIEC_LIB, "C")

SRC = """PROGRAM tontrace
VAR_INPUT
    In1 : BOOL;
END_VAR
VAR_OUTPUT
    Qo : BOOL;
END_VAR
VAR
    T1 : TON;
END_VAR
T1(IN := In1, PT := T#{N}s);
Qo := T1.Q;
END_PROGRAM
"""

DRIVER = """#include "iec_std_lib.h"
TIME __CURRENT_TIME;
#include "POUS.h"
#include "POUS.c"
#include <stdio.h>
int main(void) {
  static TONTRACE inst;
  TONTRACE_init__(&inst, 0);
  long scan = 0; int a;
  while (scanf("%d", &a) == 1) {
    ++scan;
    __CURRENT_TIME.tv_sec = scan; __CURRENT_TIME.tv_nsec = 0;
    __SET_VAR(inst., IN1,, (BOOL)a);
    TONTRACE_body__(&inst);
    printf("%ld %d %lld %lld %d\\n", scan,
      (int)__GET_VAR(inst.T1.IN,),
      (long long)__GET_VAR(inst.T1.START_TIME,).tv_sec,
      (long long)__GET_VAR(inst.T1.ET,).tv_sec,
      (int)__GET_VAR(inst.T1.Q,));
  }
  return 0;
}
"""

# IN held TRUE scans 1-6, released 7-8, re-applied 9-10 (rise/expire/reset/re-rise)
IN_SEQ = [1, 1, 1, 1, 1, 1, 0, 0, 1, 1]


def c_table(n):
    with tempfile.TemporaryDirectory() as wd:
        with open(os.path.join(wd, "prog.st"), "w") as f:
            f.write(SRC.format(N=n))
        subprocess.run([MATIEC, "-I", MATIEC_LIB, "-T", wd, "prog.st"],
                       cwd=wd, check=True, capture_output=True)
        with open(os.path.join(wd, "driver.c"), "w") as f:
            f.write(DRIVER)
        subprocess.run(["gcc", "-I", MATIEC_C, "-o", "driver", "driver.c"],
                       cwd=wd, check=True, capture_output=True)
        r = subprocess.run(["./driver"], input="\n".join(map(str, IN_SEQ)),
                           capture_output=True, text=True, cwd=wd, check=True)
    return [tuple(int(x) for x in line.split()) for line in r.stdout.strip().splitlines()]


def interp_table(n):
    prog = parse_program(SRC.format(N=n))
    st = interp.initial_state(prog)
    rows = []
    for k, a in enumerate(IN_SEQ, 1):
        st["In1"] = bool(a)
        interp.run_scan(prog, st)
        rows.append((k, int(st["In1"]), st["T1.ET"], int(st["T1.Q"])))
    return rows


def main():
    print("# TON trace tables (unchanged literal source; driver clock = scan index,")
    print("# set BEFORE the FB call; dt = 1 s per scan). SMV counter == interpreter")
    print("# counter by shared recurrence (proven per-program by the SMV trace leg).\n")
    for n in (1, 2, 3):
        print(f"## PT = T#{n}s")
        print("scan IN | C.START C.ET C.Q | interp.ET interp.Q(=SMV)")
        ct, it = c_table(n), interp_table(n)
        for (scan, cin, cstart, cet, cq), (_, _, iet, iq) in zip(ct, it):
            print(f"{scan:4d} {cin:2d} | {cstart:7d} {cet:4d} {cq:3d} | {iet:9d} {iq:8d}")
        cq_first = next((s for (s, i, st_, et, q) in ct if q), None)
        iq_first = next((s for (s, i, et, q) in it if q), None)
        print(f"   -> Q first true: C scan {cq_first}, interpreter/SMV scan {iq_first}\n")

    # H01 invariants on MATIEC-C wall-clock traces
    print("## H01 propositional G-invariants evaluated on MATIEC-C traces")
    import analysis.difftest_translator as dt
    refs = {pid: (src, rng) for pid, src, rng in dt.pool_refs()}
    pid = next(k for k in refs if "H01" in k)
    src, ranges = refs[pid]
    prog, inputs, compare, timers, _ = dt.prog_info(src)
    names = [d.name for d in compare] + [f"{t}.Q" for t in timers]
    props = {
        "P1": lambda v: not (v["NS_G"] and v["EW_G"]),
        "P2": lambda v: not ((v["NS_G"] or v["NS_Y"]) and (v["EW_G"] or v["EW_Y"])),
        "P3": lambda v: (not (v["NS_G"] or v["NS_Y"])) or v["EW_R"],
        "P4": lambda v: (not (v["EW_G"] or v["EW_Y"])) or v["NS_R"],
    }
    traces = dt.make_traces(inputs, 12345)
    viol = {k: 0 for k in props}
    scans = 0
    with tempfile.TemporaryDirectory() as wd:
        st, det = dt.c_compile(src, prog, inputs, compare, timers, wd)
        assert st == "ok", det
        for tr in traces:
            ct = dt.c_run(inputs, tr, wd)
            for row in ct:
                v = dict(zip(names, [bool(x) for x in row]))
                scans += 1
                for k, f in props.items():
                    if not f(v):
                        viol[k] += 1
    print(f"scans checked: {scans}; violations per property: {viol}")


if __name__ == "__main__":
    main()
