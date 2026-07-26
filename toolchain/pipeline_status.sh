#!/usr/bin/env bash
# Claude Code status-line: shows the currently-running experiment, the live step,
# progress, and a self-calibrating ETA for the whole 8-experiment pipeline.
# Reads results/train_STATUS.log (master) + results/exp7/STATUS.log (inference).
REPO="/home/user/Downloads/PLCCodeGenResearch"
cat >/dev/null 2>&1   # consume the session JSON Claude Code pipes in (unused)
python3 - "$REPO" <<'PY' 2>/dev/null
import os, sys, re, time, glob
repo = sys.argv[1]
S = os.path.join(repo, "results/train_STATUS.log")
E7 = os.path.join(repo, "results/exp7/STATUS.log")

def lines(p):
    try:
        return open(p).read().splitlines()
    except Exception:
        return []

def label(step):
    if step.startswith(("rlfunc_", "exp1_select")): return "Exp1b/6 functional RL"
    if step.startswith(("abl_", "exp2")):           return "Exp2 filtering ablation"
    if step.startswith(("rep_", "exp5")):           return "Exp5 repair controls"
    if step.startswith(("ent_", "exp3")):           return "Exp3 entropy-causal"
    if step.startswith("exp4"):                     return "Exp4 five-seed"
    if step.startswith(("sftlite", "rllite", "base")): return "Exp4 five-seed"
    if step.startswith(("base_infer", "sft_infer")): return "Exp7 inference baselines"
    return "training"

ml = lines(S)
done = sum(1 for l in ml if (" OK " in l or " FAIL " in l))
fails = sum(1 for l in ml if " FAIL " in l)
TOTAL = 104  # master steps: Exp1b/6 19 + Exp2 32 + Exp5 39 + Exp3 4 + Exp4 10

# completion is determined by deterministic log markers, NOT pgrep (a pgrep on a
# literal script name self-matches the shell running the check -> false "alive").
master_done = any("NEW TRAINING DONE" in l for l in ml)
e7_lines = lines(E7)
exp7_done = any("EXP7 DONE" in l for l in e7_lines)
master_alive = not master_done
exp7_alive   = master_done and not exp7_done

# current step = last START without a following OK/FAIL
cur = None; cur_ts = None
for l in ml:
    m = re.match(r"\[(\d\d:\d\d:\d\d)Z\] START (\S+)", l)
    if m: cur, cur_ts = m.group(2), m.group(1)
    m2 = re.match(r"\[(\d\d:\d\d:\d\d)Z\] (?:OK|FAIL)\s+(\S+)", l)
    if m2 and m2.group(2) == cur: cur = None

# within-step progress from the step's own log (RL/SFT show N/xx)
prog = ""
if cur:
    for lg in glob.glob(os.path.join(repo, f"results/logs_{cur}.log")):
        try:
            t = open(lg, errors="replace").read()
            mm = re.findall(r"(\d+)/(\d+) \[", t)
            if mm: prog = f" · {mm[-1][0]}/{mm[-1][1]}"
        except Exception:
            pass

# phase-aware ETA: remaining time = sum over phases of (units left x typical minutes),
# counted from result files already produced (accurate despite very uneven step costs).
def n(g):
    return len(glob.glob(os.path.join(repo, g)))
RL_EVAL, SFT_EVAL, SFT_REP, RL20, POOL, INFER = 46, 16, 14, 17, 35, 20
rem = 0.0
# Exp1b/6: 9 RL+eval runs (3 sftlite + 3 base + 3 sft)
rl_done = n("results/exp1b/rlfunc_sftlite_s*.json") + n("results/exp6/rlfunc_base_s*.json") + n("results/exp6/rlfunc_sft_s*.json")
rem += max(0, 9 - rl_done) * RL_EVAL
# Exp2: pool (+datasets) + 15 SFT+eval
if not os.path.exists(os.path.join(repo, "finetune/data/pool_model.jsonl")): rem += POOL
rem += max(0, 15 - n("results/exp2/abl_*_s*.json")) * SFT_EVAL
# Exp5: 18 SFT+repeval + 3 base repeval
rem += max(0, 18 - (n("results/exp5/rep_*_s*.json") - n("results/exp5/rep_base_s*.json"))) * SFT_REP
rem += max(0, 3 - n("results/exp5/rep_base_s*.json")) * 4
# Exp3: 4 short RL
rem += max(0, 4 - n("results/exp3/*.json")) * RL20
# Exp4: 2 RL-lite (+eval) + 2 SFT-lite (+eval) + base evals  (~128 min budget)
rem += max(0, 128 - (n("results/exp1a/rllite_s3.json")+n("results/exp1a/rllite_s4.json"))*46)
# Exp7: 6 inference-baseline runs
rem += max(0, 6 - n("results/exp7/*_infer_s*.json")) * INFER

now = time.gmtime()
now_s = now.tm_hour*3600 + now.tm_min*60 + now.tm_sec
eta_s = rem * 60
tgt = time.gmtime(time.time() + eta_s)
dd = f"{tgt.tm_mon}/{tgt.tm_mday}"
eta_txt = f"~{rem/60:.1f}h (≈{tgt.tm_hour:02d}:{tgt.tm_min:02d}Z {dd})"

def secs(hms):
    h, mi, s = map(int, hms.split(":")); return h*3600 + mi*60 + s
nowz = f"{now.tm_hour:02d}:{now.tm_min:02d}Z"
if not master_alive and exp7_alive:
    e7 = lines(E7); e7cur = ""
    for l in e7:
        m = re.match(r"\[(\d\d:\d\d:\d\d)Z\] START (\S+)", l)
        if m: e7cur = m.group(2)
    print(f"⚙ Exp7 inference baselines · {e7cur} | master done ({done}/{TOTAL}) | {nowz}")
elif not master_alive and not exp7_alive and done >= TOTAL:
    print(f"✅ ALL 8 EXPERIMENTS DONE ({done} steps, {fails} fail) · ready for paper fold-in | {nowz}")
elif cur:
    since = ""
    if cur_ts:
        el2 = (now_s - secs(cur_ts)) % 86400
        since = f" · {el2//60}m"
    print(f"⚙ {label(cur)} · {cur}{prog}{since} | {done}/{TOTAL} steps, {fails} fail | ETA {eta_txt}")
else:
    st = "running" if master_alive else "idle"
    print(f"⚙ pipeline {st} · {done}/{TOTAL} steps, {fails} fail | ETA {eta_txt} | {nowz}")
PY
