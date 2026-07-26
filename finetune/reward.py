"""Verifier reward: turn the dual oracle into a scalar training signal.

Graded so RL gets gradient, with compilation and safety both required for full
reward:
    0.0   not parseable by the verification front-end
    0.1   parses but does not compile (MATIEC)
    0.3 + 0.7 * (props_passed / props)   compiles; scaled by formal safety
=> a verified-safe program (compiles AND all properties hold) scores 1.0.

Requires nuXmv (+ MATIEC) available, i.e. run on the toolchain box. Used by rl.py.
"""
from __future__ import annotations

from plcbench.schema import Task
from plcbench.harness import evaluate
from plcbench.st import STSyntaxError
from plcbench.st.parser import parse_program
from plcbench.generate.extract import extract_st


def dual_oracle_reward(meta: dict, completion: str) -> float:
    # The whole body is guarded: during RL the policy can emit arbitrary bytes, and
    # a single malformed completion must never crash training -> reward 0.0 instead.
    try:
        code = extract_st(completion)
        try:
            parse_program(code)
        except (STSyntaxError, Exception):
            return 0.0
        task = Task.model_validate(meta)
        ev = evaluate(task, code)
        if ev.compiles is False:
            return 0.1
        frac = (ev.n_props_pass / ev.n_props) if ev.n_props else 0.0
        return round(0.3 + 0.7 * frac, 4)
    except Exception:  # noqa: BLE001 (oracle/subprocess hiccup on adversarial output)
        return 0.0


def task_valid_reward(meta: dict, completion: str) -> float:
    """FUNCTIONAL dual-oracle reward (DeepReview B1/B4): compilation AND formal
    safety invariants AND functional execution scenarios are ALL required for full
    reward, so an inert all-off controller (passes invariants, fails every
    activation scenario) can no longer be rewarded:

        0.0                        not parseable
        0.1                        parses, MATIEC-rejected
        0.2 + 0.4*prop + 0.4*scen  compiles; graded by safety AND functional pass
    => 1.0 iff compiles + all invariants hold + all scenarios pass.

    Falls back to the invariant-only grading when the task carries no scenarios,
    so it is safe on tasks that were never given a functional oracle.
    """
    try:
        code = extract_st(completion)
        try:
            parse_program(code)
        except (STSyntaxError, Exception):
            return 0.0
        task = Task.model_validate(meta)
        ev = evaluate(task, code)
        # fail-closed: only a genuine MATIEC accept (True) counts as compiling; an
        # unavailable compiler (None) must not be read as success.
        if ev.compiles is not True:
            return 0.1
        prop = (ev.n_props_pass / ev.n_props) if ev.n_props else 0.0
        if ev.scenarios_total <= 0:
            # No functional oracle: grade on invariants but CAP below 1.0 so an inert
            # all-off program can never earn full reward on a scenario-less task.
            return round(0.2 + 0.7 * prop, 4)
        scen = ev.scenarios_pass / ev.scenarios_total
        return round(0.2 + 0.4 * prop + 0.4 * scen, 4)
    except Exception:  # noqa: BLE001
        return 0.0


# ---------------------------------------------------------------------------
# CRITICAL-PROPERTY HARD-GATED task-valid reward (added alongside; the functions
# above are NOT modified).
#
# Motivation: the graded task_valid_reward gives partial credit (0.2 + 0.4*prop +
# 0.4*scen) even when a SAFETY-CRITICAL invariant is violated -- a program that
# breaks an emergency-stop interlock but passes everything else can still earn a
# high reward. In a safety context a violated *critical* property should never earn
# more than the no-compile floor. This variant HARD-GATES: if ANY property whose
# severity is 'critical' fails to verify, the reward is capped at 0.1; otherwise it
# is exactly the task_valid_reward score.
#
# Severity truth (verified against benchmark/tasks/*/meta.json, plcbench.schema
# Severity enum = {critical, high, medium}): all 22 benchmark tasks carry >=1
# 'critical' property (36 of 71 properties are critical). So the 'critical' gate is
# well-defined and active on every task -- no need to fall back to gating on ALL
# properties. See docs/14_VM_PLAN.md for the per-task counts.
# ---------------------------------------------------------------------------


def _critical_property_ids(task) -> set:
    """IDs of properties whose severity is 'critical' (handles Enum or raw str)."""
    return {p.id for p in task.safety_properties
            if getattr(p.severity, "value", p.severity) == "critical"}


def _any_critical_failed(task, ev) -> bool:
    """True iff some critical property is not a CONFIRMED pass in this evaluation.

    Fail-closed: a critical property counts as failed unless the model-checker
    explicitly returned status 'pass' for it (an unavailable/error/unknown verify
    result is treated as a critical failure, never as success).
    """
    crit = _critical_property_ids(task)
    if not crit:
        return False  # no critical props on this task -> nothing to gate
    status = {}
    vr = getattr(ev, "verify", None)
    if vr is not None:
        status = {pr.property_id: pr.status for pr in vr.properties}
    return any(status.get(pid) != "pass" for pid in crit)


def _taskvalid_score_from_eval(ev) -> float:
    """The graded task-valid score for an evaluation (mirror of task_valid_reward's
    scoring, factored out so it can be unit-tested with a mocked eval object).
    Assumes the completion already parsed."""
    if ev.compiles is not True:
        return 0.1
    prop = (ev.n_props_pass / ev.n_props) if ev.n_props else 0.0
    if ev.scenarios_total <= 0:
        return round(0.2 + 0.7 * prop, 4)
    scen = ev.scenarios_pass / ev.scenarios_total
    return round(0.2 + 0.4 * prop + 0.4 * scen, 4)


def reward_taskvalid_gated(meta: dict, completion: str) -> float:
    """CRITICAL-PROPERTY HARD-GATED task-valid reward.

        0.0                         not parseable
        0.1                         parses but MATIEC-rejected, OR any 'critical'
                                    safety property fails to verify (hard gate)
        task_valid_reward score     otherwise (compile + graded safety + scenarios)

    => identical to task_valid_reward EXCEPT a violated critical property can never
    score above 0.1, regardless of how many other properties/scenarios pass.
    """
    try:
        code = extract_st(completion)
        try:
            parse_program(code)
        except (STSyntaxError, Exception):
            return 0.0
        task = Task.model_validate(meta)
        ev = evaluate(task, code)
        base = _taskvalid_score_from_eval(ev)
        if _any_critical_failed(task, ev):
            return min(base, 0.1)
        return base
    except Exception:  # noqa: BLE001 (oracle/subprocess hiccup on adversarial output)
        return 0.0


def batch_reward(metas, completions):
    return [dual_oracle_reward(m, c) for m, c in zip(metas, completions)]
