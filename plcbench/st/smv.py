"""Translate the ST subset to an SMV model for nuXmv.

Scan-cycle encoding (faithful PLC semantics):
  - inputs            -> free VARs (nondeterministic each cycle), bounded for INT
  - outputs/internals -> a stored previous-scan VAR `<v>__prev` plus a DEFINE `<v>`
    giving the CURRENT-scan value as a function of current inputs and *__prev.
    next(<v>__prev) := <v>.  Properties reference `<v>` (the current output).
  - constants are inlined as literals.
  - TON timers (discrete time = scan ticks): instance T with preset PT becomes a
    counter `T__ET__prev` (0..PT). When IN is false ET resets to 0; while IN true
    ET counts up to PT; Q := IN & ET>=PT.  Reads of `T.Q` / `T.ET` resolve to the
    current-scan DEFINEs.  TON calls must be at the program-body top level (gate
    via the IN expression), so the counter update is unconditional and sound.
  - CASE becomes a nested SMV `case` keyed on equality with the selector.

The ST body is symbolically executed: a read of a variable resolves to its
already-updated value if assigned earlier this scan, else its previous-scan value.
"""
from __future__ import annotations

from ..schema import Task
from .parser import (Assign, Binary, Case, If, Lit, Program, TimerCall, Unary,
                     Var, parse_program)

_BINOP = {
    "AND": "&", "OR": "|", "=": "=", "<>": "!=", "<": "<", "<=": "<=",
    ">": ">", ">=": ">=", "+": "+", "-": "-", "*": "*", "MOD": "mod",
}


class SMVTranslateError(Exception):
    pass


def _lit(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def expr_to_smv(node, env: dict) -> str:
    if isinstance(node, Lit):
        return _lit(node.value)
    if isinstance(node, Var):
        return env.get(node.name, node.name)
    if isinstance(node, Unary):
        inner = expr_to_smv(node.operand, env)
        return f"(!{inner})" if node.op == "NOT" else f"(-{inner})"
    if isinstance(node, Binary):
        l = expr_to_smv(node.left, env)
        r = expr_to_smv(node.right, env)
        return f"({l} {_BINOP[node.op]} {r})"
    raise SMVTranslateError(f"cannot translate node {node!r}")


def _const_int(node, consts: dict) -> int:
    if isinstance(node, Lit) and isinstance(node.value, int):
        return node.value
    if isinstance(node, Var) and node.name in consts:
        return int(consts[node.name])
    raise SMVTranslateError(f"PT must be an integer literal or CONSTANT, got {node!r}")


def _collect_assigned(stmts, out: set):
    for s in stmts:
        if isinstance(s, Assign):
            out.add(s.target)
        elif isinstance(s, If):
            for _, body in s.branches:
                _collect_assigned(body, out)
            _collect_assigned(s.orelse, out)
        elif isinstance(s, Case):
            for _, body in s.branches:
                _collect_assigned(body, out)
            _collect_assigned(s.orelse, out)
        # TimerCall assigns no plain variable (handled separately)


def _build_case(cases: list, default: str) -> str:
    parts = [f"{c} : {v};" for c, v in cases]
    parts.append(f"TRUE : {default};")
    return "case " + " ".join(parts) + " esac"


def symexec(stmts, env: dict, ctx: dict, top_level: bool = True) -> None:
    for s in stmts:
        if isinstance(s, Assign):
            env[s.target] = expr_to_smv(s.expr, env)

        elif isinstance(s, TimerCall):
            if not top_level:
                raise SMVTranslateError(
                    "TON calls must be at the program-body top level (gate via IN)")
            in_smv = expr_to_smv(s.in_expr, env)
            pt = _const_int(s.pt, ctx["consts"])
            inst = s.instance
            etp = f"{inst}__ET__prev"
            et_expr = f"case !({in_smv}) : 0; {etp} < {pt} : {etp} + 1; TRUE : {pt}; esac"
            q_expr = f"(({in_smv}) & ({inst}__ET >= {pt}))"
            ctx["timers"][inst] = {"pt": pt, "et": et_expr, "q": q_expr}
            env[f"{inst}.ET"] = f"{inst}__ET"
            env[f"{inst}.Q"] = f"{inst}__Q"

        elif isinstance(s, If):
            pre = dict(env)
            assigned: set = set()
            _collect_assigned([s], assigned)
            branch_results = []
            for cond, body in s.branches:
                cond_smv = expr_to_smv(cond, pre)
                benv = dict(pre)
                symexec(body, benv, ctx, top_level=False)
                branch_results.append((cond_smv, benv))
            else_env = dict(pre)
            symexec(s.orelse, else_env, ctx, top_level=False)
            for v in assigned:
                cases = [(c, benv.get(v, pre.get(v, v))) for c, benv in branch_results]
                env[v] = _build_case(cases, else_env.get(v, pre.get(v, v)))

        elif isinstance(s, Case):
            pre = dict(env)
            assigned = set()
            _collect_assigned([s], assigned)
            sel = expr_to_smv(s.selector, pre)
            branch_results = []
            for labels, body in s.branches:
                cond = " | ".join(f"({sel} = {lab})" for lab in sorted(labels))
                benv = dict(pre)
                symexec(body, benv, ctx, top_level=False)
                branch_results.append((cond, benv))
            else_env = dict(pre)
            symexec(s.orelse, else_env, ctx, top_level=False)
            for v in assigned:
                cases = [(c, benv.get(v, pre.get(v, v))) for c, benv in branch_results]
                env[v] = _build_case(cases, else_env.get(v, pre.get(v, v)))

        else:
            raise SMVTranslateError(f"cannot translate statement {s!r}")


def _smv_type(name: str, typ: str, ranges: dict) -> str:
    if typ == "BOOL":
        return "boolean"
    if typ == "INT":
        rng = ranges.get(name)
        if rng is None:
            raise SMVTranslateError(
                f"INT variable {name!r} needs a [min,max] range to be model-checkable")
        return f"{int(rng[0])}..{int(rng[1])}"
    raise SMVTranslateError(f"unsupported type {typ!r}")


def _is_ctl(formula: str) -> bool:
    return any(op in formula for op in ("AG", "EF", "AX", "EX", "AF", "EG", "A[", "E["))


def _normalize_formula(f: str) -> str:
    return (f.replace(" AND ", " & ").replace(" OR ", " | ")
             .replace(" NOT ", " !").replace("<>", "!="))


def model_smv(prog: Program, task: Task) -> str:
    ranges = {v.name: v.range for v in task.interface if v.range}
    decls = prog.decls
    consts = {d.name: d.init for d in decls if d.const}
    inputs = [d for d in decls if d.direction == "input" and not d.const and d.type != "TON"]
    states = [d for d in decls if d.direction in ("output", "internal")
              and not d.const and d.type != "TON"]
    timer_decls = [d for d in decls if d.type == "TON"]

    env = {}
    for d in inputs:
        env[d.name] = d.name
    for d in states:
        env[d.name] = f"{d.name}__prev"
    for d in consts:
        env[d] = _lit(consts[d])
    # Pre-seed reads that occur BEFORE a timer's call in scan order with the
    # previous-scan values (matching the interpreter): ET reads resolve to the
    # stored counter, and since ET__prev > 0 iff IN was true on the previous
    # scan, the previous-scan Q is exactly (ET__prev >= PT) for PT >= 1. The
    # preset is prescanned from the (top-level) call. A constant-FALSE Q
    # pre-seed here was a real defect caught by the SMV trace leg of the
    # differential validation (read-before-call programs only; see paper).
    prescanned_pt = {}
    for s in prog.body:
        if isinstance(s, TimerCall):
            try:
                prescanned_pt[s.instance] = _const_int(s.pt, consts)
            except SMVTranslateError:
                pass
    for d in timer_decls:
        env[f"{d.name}.ET"] = f"{d.name}__ET__prev"
        pt0 = prescanned_pt.get(d.name)
        env[f"{d.name}.Q"] = (f"({d.name}__ET__prev >= {pt0})"
                              if pt0 and pt0 >= 1 else "FALSE")

    ctx = {"timers": {}, "consts": consts}
    symexec(prog.body, env, ctx)
    timers = ctx["timers"]

    lines = ["MODULE main", "VAR"]
    for d in inputs:
        lines.append(f"  {d.name} : {_smv_type(d.name, d.type, ranges)};")
    for d in states:
        lines.append(f"  {d.name}__prev : {_smv_type(d.name, d.type, ranges)};")
    for inst, t in timers.items():
        lines.append(f"  {inst}__ET__prev : 0..{t['pt']};")

    lines.append("DEFINE")
    for d in states:
        lines.append(f"  {d.name} := {env[d.name]};")
    for inst, t in timers.items():
        lines.append(f"  {inst}__ET := {t['et']};")
        lines.append(f"  {inst}__Q := {t['q']};")

    lines.append("ASSIGN")
    for d in states:
        default = _lit(d.init) if d.init is not None else (
            "FALSE" if d.type == "BOOL" else str(int(ranges.get(d.name, [0, 0])[0])))
        lines.append(f"  init({d.name}__prev) := {default};")
        lines.append(f"  next({d.name}__prev) := {d.name};")
    for inst in timers:
        lines.append(f"  init({inst}__ET__prev) := 0;")
        lines.append(f"  next({inst}__ET__prev) := {inst}__ET;")

    return "\n".join(lines) + "\n"


def spec_line(prop) -> str:
    formula = _normalize_formula(prop.ltl or prop.ctl or "")
    kw = "CTLSPEC" if (prop.ctl and not prop.ltl) or _is_ctl(formula) else "LTLSPEC"
    return f"{kw} {formula}"


def translate(prog: Program, task: Task) -> str:
    out = [model_smv(prog, task)]
    for p in task.safety_properties:
        out.append(f"-- {p.id} [{p.severity.value}] {p.nl}")
        out.append(spec_line(p))
    return "\n".join(out) + "\n"


def translate_src(st_src: str, task: Task) -> str:
    return translate(parse_program(st_src), task)
