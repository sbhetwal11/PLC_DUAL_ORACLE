"""Counterexample-repair training pairs.

The method's signature is the *formal* verifier in the loop. Here we turn it into
supervised repair data: take a dual-oracle-verified reference, inject a realistic
safety bug, run the oracle to obtain a real nuXmv counterexample, and emit a pair

    prompt    = spec + the failing attempt + the counterexample (verifier feedback)
    completion= the corrected (verified) reference

so the model learns to map (spec, broken code, counterexample) -> safe code. This
module is pure (bug mutators + prompt formatting); build_sft runs the oracle and
keeps only variants that genuinely fail verification.
"""
from __future__ import annotations

import re


def weaken_or(st: str):
    """Drop one disjunct from the first multi-term `IF ... THEN` condition.

    For a de-energising branch `IF a OR b OR c THEN out := FALSE;` this removes a
    safety term, so the actuator can stay energised when it should not -> a real
    safety-property violation with a counterexample.
    """
    m = re.search(r"\bIF\s+(.+?)\s+THEN", st, flags=re.DOTALL)
    if not m:
        return None
    cond = m.group(1)
    parts = re.split(r"\s+OR\s+", cond)
    if len(parts) < 2:
        return None
    weakened = " OR ".join(parts[1:])  # drop the first disjunct
    return st[:m.start(1)] + weakened + st[m.end(1):]


def flip_compare(st: str):
    """Loosen the first `>=`/`<=` bound to `>`/`<` (off-by-one safety bug)."""
    for a, b in ((">=", ">"), ("<=", "<")):
        i = st.find(a)
        if i != -1:
            return st[:i] + b + st[i + len(a):]
    return None


def force_true(st: str):
    """Flip a de-energising `:= FALSE;` to `:= TRUE;` (fails a 'forces off' prop)."""
    i = st.find(":= FALSE;")
    if i == -1:
        return None
    return st[:i] + ":= TRUE;" + st[i + len(":= FALSE;"):]


MUTATORS = {"weaken_or": weaken_or, "flip_compare": flip_compare, "force_true": force_true}


def bug_variants(st: str, names=None):
    """Candidate buggy mutations of a verified program (deduped, non-empty).

    names: optional subset of MUTATORS to use (for held-out bug-type experiments)."""
    fns = [MUTATORS[n] for n in names] if names else list(MUTATORS.values())
    out, seen = [], set()
    for fn in fns:
        v = fn(st)
        if v and v != st and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def variant_prompt(kind, base_prompt, bad_st, pid, nl, cex, shuffled_cex=None):
    """Repair-prompt controls (DeepReview M19). All share spec + failing attempt;
    they differ only in the FEEDBACK signal appended:
        full        real counterexample trace (the method)
        nocex       no feedback beyond 'it failed verification'
        proponly    the violated property, no trace
        erroronly   a generic verifier-error string, no trace/property
        shuffle     a real trace, but from a DIFFERENT task (mismatched)
    """
    # Every variant shares _repair_head (spec + buggy attempt); they differ ONLY in
    # the feedback sentence, so full-vs-* is a single-variable control (B3 fix).
    head = _repair_head(base_prompt, bad_st)
    if kind == "full":
        return repair_prompt(base_prompt, bad_st, pid, nl, cex)
    if kind == "shuffle":
        return repair_prompt(base_prompt, bad_st, pid, nl, shuffled_cex or cex)
    if kind == "nocex":
        fb = ""
    elif kind == "proponly":
        fb = f"It violates safety property {pid} ({nl}). "
    elif kind == "erroronly":
        fb = "The model checker reported: PROPERTY VIOLATED (no trace available). "
    else:
        raise ValueError(kind)
    return head + fb + _TAIL


def _repair_head(base_prompt: str, bad_st: str) -> str:
    """Shared prefix for every repair prompt: spec + the failing attempt. All
    feedback-channel controls (M19) append to THIS so they differ in exactly one
    thing -- the feedback -- not in whether the buggy code is shown."""
    return (f"{base_prompt}\n\n---\nA previous attempt FAILED formal verification:\n\n"
            f"{bad_st}\n\n")


_TAIL = ("Return a corrected IEC 61131-3 ST program that satisfies ALL safety "
         "properties. Output only the corrected program.")


def repair_prompt(base_prompt: str, bad_st: str, failing_pid: str,
                  failing_nl: str, cex: str) -> str:
    """Full repair prompt: spec + failed attempt + the formal counterexample."""
    cex = (cex or "").strip()
    if len(cex) > 1500:
        cex = cex[:1500] + "\n... (trace truncated)"
    return (f"{_repair_head(base_prompt, bad_st)}The model checker refuted safety "
            f"property {failing_pid} ({failing_nl}) with this counterexample trace:\n\n"
            f"{cex}\n\n{_TAIL}")
