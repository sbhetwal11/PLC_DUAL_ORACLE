"""Benchmark well-formedness tests. Run: pytest -q

These check the benchmark is internally consistent and the harness runs
end-to-end on a bare machine (no MATIEC/nuXmv needed).
"""
import re

from plcbench.loader import load_all
from plcbench.harness import evaluate_loaded
from plcbench.backends.compile_matiec import compile_st

_KEYWORDS = {"G", "F", "X", "U", "R", "AG", "EF", "AF", "EG",
             "TRUE", "FALSE", "AND", "OR", "NOT"}


def _idents(s: str):
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s))


def test_tasks_load():
    tasks = load_all()
    assert len(tasks) >= 3, "expected at least the seed tasks"


def test_each_task_well_formed():
    for lt in load_all():
        t = lt.task
        assert t.id, "task needs an id"
        assert t.safety_properties, f"{t.id}: needs >=1 safety property"
        assert lt.reference_st.strip(), f"{t.id}: empty reference ST"
        names = {v.name for v in t.interface}
        for p in t.safety_properties:
            formula = f"{p.ltl or ''} {p.ctl or ''}"
            for tok in _idents(formula):
                if tok in _KEYWORDS:
                    continue
                assert tok in names, f"{t.id}/{p.id}: unknown var '{tok}' in formula"


def test_reference_mentions_program_name():
    # the reference ST should declare a PROGRAM (sanity, not a full parse)
    for lt in load_all():
        assert "PROGRAM" in lt.reference_st.upper(), f"{lt.id}: no PROGRAM block"


def test_harness_runs_on_references():
    for lt in load_all():
        ev = evaluate_loaded(lt)
        assert ev.task_id == lt.id
        assert ev.n_props == len(lt.task.safety_properties)
        # without the toolchain, compile/verify are reported as unavailable (None)
        assert ev.compiles in (True, False, None)
        assert ev.verified in (True, False, None)


def test_basic_syntax_checker_flags_imbalance():
    bad = "PROGRAM p\nVAR\n  x : BOOL;\n(* missing END_VAR and END_PROGRAM *)\n"
    res = compile_st(bad)
    assert res.ok is False, "unbalanced blocks should fail the basic checker"


def test_basic_syntax_checker_accepts_reference():
    # the reference solutions should at least pass the structural lint
    for lt in load_all():
        res = compile_st(lt.reference_st)
        assert res.ok is True, f"{lt.id}: reference failed basic syntax lint: {res.stderr}"
