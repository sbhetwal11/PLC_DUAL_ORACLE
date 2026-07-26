"""Interpreter for the ST subset - executes scan cycles. Used for scenario-based
testing of candidate/reference solutions (and as a semantic reference to
cross-check the SMV translation).
"""
from __future__ import annotations

from .parser import (Assign, Binary, Case, If, Lit, Program, TimerCall, Unary,
                     Var, parse_program)


def initial_state(prog: Program) -> dict:
    st: dict[str, object] = {}
    for d in prog.decls:
        if d.type == "TON":
            st[f"{d.name}.ET"] = 0
            st[f"{d.name}.Q"] = False
        elif d.init is not None:
            st[d.name] = d.init
        else:
            st[d.name] = False if d.type == "BOOL" else 0
    return st


def _eval(node, st: dict):
    if isinstance(node, Lit):
        return node.value
    if isinstance(node, Var):
        if node.name not in st:
            raise KeyError(f"unknown variable {node.name!r}")
        return st[node.name]
    if isinstance(node, Unary):
        v = _eval(node.operand, st)
        return (not v) if node.op == "NOT" else (-v)
    if isinstance(node, Binary):
        l = _eval(node.left, st)
        r = _eval(node.right, st)
        op = node.op
        if op == "AND":
            return bool(l) and bool(r)
        if op == "OR":
            return bool(l) or bool(r)
        if op == "=":
            return l == r
        if op == "<>":
            return l != r
        if op == "<":
            return l < r
        if op == "<=":
            return l <= r
        if op == ">":
            return l > r
        if op == ">=":
            return l >= r
        if op == "+":
            return l + r
        if op == "-":
            return l - r
        if op == "*":
            return l * r
        if op == "MOD":
            return l % r
    raise TypeError(f"cannot evaluate node {node!r}")


def _exec(stmts, st: dict):
    for s in stmts:
        if isinstance(s, Assign):
            st[s.target] = _eval(s.expr, st)
        elif isinstance(s, If):
            done = False
            for cond, body in s.branches:
                if _eval(cond, st):
                    _exec(body, st)
                    done = True
                    break
            if not done:
                _exec(s.orelse, st)
        elif isinstance(s, Case):
            val = _eval(s.selector, st)
            matched = False
            for labels, body in s.branches:
                if val in labels:
                    _exec(body, st)
                    matched = True
                    break
            if not matched:
                _exec(s.orelse, st)
        elif isinstance(s, TimerCall):
            inv = bool(_eval(s.in_expr, st))
            pt = _eval(s.pt, st)
            et = st.get(f"{s.instance}.ET", 0)
            et = min(et + 1, pt) if inv else 0
            st[f"{s.instance}.ET"] = et
            st[f"{s.instance}.Q"] = inv and (et >= pt)
        else:
            raise TypeError(f"cannot execute statement {s!r}")


def run_scan(prog: Program, st: dict) -> dict:
    """Execute one PLC scan in place; returns the same dict for convenience."""
    _exec(prog.body, st)
    return st


def check_scenarios(prog: Program, scenarios: list) -> list:
    """Run each scenario; return list of (scenario_id, ok, detail)."""
    results = []
    for sc in scenarios:
        st = initial_state(prog)
        ok, detail = True, ""
        for k, step in enumerate(sc.steps):
            for name, val in step.inputs.items():
                st[name] = val
            run_scan(prog, st)
            for name, exp in step.expect.items():
                if st.get(name) != exp:
                    ok = False
                    detail = f"step {k}: {name}={st.get(name)} expected {exp}"
                    break
            if not ok:
                break
        results.append((sc.id, ok, detail))
    return results


def check_scenarios_src(st_src: str, scenarios: list) -> list:
    return check_scenarios(parse_program(st_src), scenarios)
