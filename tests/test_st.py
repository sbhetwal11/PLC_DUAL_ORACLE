"""Tests for the ST subset: parser, interpreter (scenario validation of the
reference solutions), and SMV translation."""
import pytest

from plcbench.loader import load_all
from plcbench.st import parse_program, STSyntaxError
from plcbench.st.smv import translate_src, model_smv
from plcbench.st.parser import parse_program as pp
from plcbench.backends.simulate import run_scenarios


def test_references_parse():
    for lt in load_all():
        prog = parse_program(lt.reference_st)
        assert prog.name, f"{lt.id}: program has no name"
        assert prog.body, f"{lt.id}: empty body"


def test_references_pass_their_own_scenarios():
    # The interpreter must confirm each reference solution satisfies its scenarios.
    for lt in load_all():
        res = run_scenarios(lt.task, lt.reference_st)
        assert res.parse_ok, f"{lt.id}: reference failed to parse: {res.detail}"
        assert res.passed == res.total, (
            f"{lt.id}: reference failed scenarios "
            f"({res.passed}/{res.total}): {res.detail} :: {res.per_scenario}")


def test_smv_generation_for_all_tasks():
    for lt in load_all():
        smv = translate_src(lt.reference_st, lt.task)
        assert "MODULE main" in smv
        assert "ASSIGN" in smv
        # one SPEC per safety property
        n_spec = smv.count("LTLSPEC") + smv.count("CTLSPEC")
        assert n_spec == len(lt.task.safety_properties), f"{lt.id}: spec count mismatch"


def test_smv_motor_encoding_shape():
    lt = next(x for x in load_all() if x.id == "E01_motor_interlock")
    smv = model_smv(pp(lt.reference_st), lt.task)
    assert "Motor__prev" in smv
    assert "next(Motor__prev) := Motor;" in smv
    assert "DEFINE" in smv and "Motor :=" in smv


def test_parser_rejects_unsupported():
    with pytest.raises(STSyntaxError):
        parse_program("PROGRAM p VAR x : REAL; END_VAR END_PROGRAM")


def test_buggy_solution_fails_scenarios():
    # a motor controller that ignores the emergency stop must fail E01 scenarios
    lt = next(x for x in load_all() if x.id == "E01_motor_interlock")
    buggy = (
        "PROGRAM motor_interlock\n"
        "VAR_INPUT Start:BOOL; Stop:BOOL; EStop:BOOL; END_VAR\n"
        "VAR_OUTPUT Motor:BOOL; END_VAR\n"
        "IF Stop THEN Motor := FALSE; ELSIF Start THEN Motor := TRUE; END_IF;\n"
        "END_PROGRAM\n"
    )
    res = run_scenarios(lt.task, buggy)
    assert res.parse_ok
    assert res.passed < res.total, "buggy code should fail at least one scenario"
