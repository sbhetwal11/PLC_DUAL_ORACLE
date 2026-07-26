"""ITEM 8 (reachability proof): a program MATIEC COMPILES but the ST->SMV translator
CANNOT encode -> harness category 'translate_error' -> what does Eq.(2) actually pay?

Runs the REAL dual_oracle_reward / task_valid_reward (real MATIEC + real nuXmv, no
mocking) on an E01 variant that adds an unranged INT internal (legal ST, MATIEC-OK,
but smv._smv_type raises 'INT variable needs a [min,max] range').
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.harness import evaluate
from plcbench.schema import Task
from plcbench.generate.evaluate import _categorize
from plcbench.st import STSyntaxError
from plcbench.st.parser import parse_program
from finetune.reward import dual_oracle_reward, task_valid_reward, reward_taskvalid_gated

META = json.load(open("benchmark/tasks/easy/E01_motor_interlock/meta.json", encoding="utf-8"))

CODE = """PROGRAM motor_interlock
VAR_INPUT
    Start : BOOL;
    Stop  : BOOL;
    EStop : BOOL;
END_VAR
VAR_OUTPUT
    Motor : BOOL;
END_VAR
VAR
    Cnt : INT;
END_VAR
IF NOT EStop THEN
    Motor := FALSE;
ELSIF Stop THEN
    Motor := FALSE;
ELSIF Start THEN
    Motor := TRUE;
END_IF;
Cnt := Cnt + 1;
END_PROGRAM
"""

task = Task.model_validate(META)
try:
    parse_program(CODE); parsed = True
except (STSyntaxError, Exception) as e:
    parsed = False; print("parse err:", e)
ev = evaluate(task, CODE)
cat = _categorize(parsed, ev)
print("parsed:", parsed)
print("compiles:", ev.compiles, " (True = MATIEC accepted)")
print("verify available:", ev.verify.available if ev.verify else None,
      " property statuses:", [p.status for p in ev.verify.properties] if ev.verify else None)
print("n_props:", ev.n_props, " n_props_pass:", ev.n_props_pass,
      " scenarios:", ev.scenarios_pass, "/", ev.scenarios_total)
print("harness category:", cat)
print("-" * 50)
print("dual_oracle_reward   (Eq 2):", dual_oracle_reward(META, CODE))
print("task_valid_reward    (Eq 3):", task_valid_reward(META, CODE))
print("reward_taskvalid_gated     :", reward_taskvalid_gated(META, CODE))
print("-" * 50)
print("PAPER Sec S.XVI claims translate_error -> 0.0 ; ACTUAL dual reward printed above")
