"""Tests for the Phase-C generation/eval pipeline (no API key needed)."""
from plcbench.generate.extract import extract_st
from plcbench.generate.prompt import build_prompt
from plcbench.generate.clients import ReferenceGenerator, make_generator
from plcbench.generate.evaluate import run_eval
from plcbench.loader import load_all


def test_extract_from_fenced():
    txt = "Here you go:\n```iecst\nPROGRAM p\nVAR x:BOOL; END_VAR\nEND_PROGRAM\n```\nDone."
    st = extract_st(txt)
    assert st.startswith("PROGRAM") and st.endswith("END_PROGRAM")


def test_extract_from_prose():
    txt = "blah PROGRAM q VAR_OUTPUT y:BOOL; END_VAR y := TRUE; END_PROGRAM trailing"
    st = extract_st(txt)
    assert "PROGRAM q" in st and st.endswith("END_PROGRAM")


def test_prompt_lists_interface():
    lt = next(iter(load_all()))
    p = build_prompt(lt.task)
    for v in lt.task.interface:
        assert v.name in p


def test_make_generator_reference():
    g = make_generator("reference")
    assert isinstance(g, ReferenceGenerator) and g.available()


def test_make_generator_providers():
    # all four provider specs construct and expose name + availability
    for spec in ("anthropic:claude-x", "openai:gpt-x", "grok:grok-x", "gemini:gemini-x"):
        g = make_generator(spec)
        assert g.name == spec
        assert isinstance(g.available(), bool)  # False unless that key is set


def test_make_generator_rejects_bad_spec():
    import pytest
    with pytest.raises(ValueError):
        make_generator("notaprovider:model")


def test_pass_at_k_math():
    from plcbench.generate.evaluate import pass_at_k
    assert pass_at_k(5, 5, 1) == 1.0          # all correct
    assert pass_at_k(5, 0, 1) == 0.0          # none correct
    assert pass_at_k(5, 0, 5) == 0.0
    assert abs(pass_at_k(5, 1, 3) - 0.6) < 1e-9   # 1 - C(4,3)/C(5,3)
    assert pass_at_k(3, 1, 5) == 1.0          # k clamped to n; n-c<k


def test_run_eval_passk_reference():
    from plcbench.generate.evaluate import run_eval_passk
    rep = run_eval_passk(ReferenceGenerator(), n_samples=2, ks=[1, 2], temperature=0.0)
    s = rep.summary()
    assert s["tasks"] >= 22 and s["n_samples"] == 2
    assert 0.0 <= s["pass@1"] <= 1.0 and 0.0 <= s["pass@2"] <= 1.0


def test_run_eval_reference_scenarios():
    # reference solutions must pass all scenarios through the eval pipeline
    rep = run_eval(ReferenceGenerator())
    s = rep.summary()
    assert s["tasks"] >= 18
    assert s["api_errors"] == 0
    assert s["scenario_pass_rate"] == 1.0
    # references parse fine; without nuXmv on this host they are 'verify_unavailable'
    assert all(r.category in ("verified", "verify_unavailable") for r in rep.rows)
