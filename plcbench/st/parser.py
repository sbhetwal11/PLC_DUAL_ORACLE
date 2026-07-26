"""Tokenizer + recursive-descent parser for the supported ST subset.

Produces a small AST (dataclasses below). Raises STSyntaxError for anything
outside the supported grammar so unsupported code is rejected loudly rather than
mis-translated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class STSyntaxError(Exception):
    pass


# ---------------------------------------------------------------- AST nodes
@dataclass
class VarDecl:
    name: str
    type: str          # "BOOL" | "INT"
    direction: str     # "input" | "output" | "internal"
    const: bool = False
    init: object = None  # bool | int | None


@dataclass
class Var:
    name: str


@dataclass
class Lit:
    value: object       # bool | int


@dataclass
class Unary:
    op: str             # "NOT" | "-"
    operand: object


@dataclass
class Binary:
    op: str             # AND OR + - * MOD = <> < <= > >=
    left: object
    right: object


@dataclass
class Assign:
    target: str
    expr: object


@dataclass
class TimerCall:
    instance: str          # TON instance name
    in_expr: object        # IN := <expr>
    pt: object             # PT := <expr> (integer ticks)


@dataclass
class Case:
    selector: object
    branches: list         # list[(set[int] labels, list[stmt])]
    orelse: list = field(default_factory=list)


@dataclass
class If:
    branches: list      # list[(cond, list[stmt])]
    orelse: list = field(default_factory=list)


@dataclass
class Program:
    name: str
    decls: list         # list[VarDecl]
    body: list          # list[stmt]

    def decl(self, name):
        return next((d for d in self.decls if d.name == name), None)


# ---------------------------------------------------------------- tokenizer
_KEYWORDS = {
    "PROGRAM", "END_PROGRAM", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR",
    "CONSTANT", "END_VAR", "IF", "THEN", "ELSIF", "ELSE", "END_IF",
    "CASE", "OF", "END_CASE", "TON",
    "BOOL", "INT", "TRUE", "FALSE", "AND", "OR", "NOT", "MOD",
}
# multi-char operators first
_OPS = [":=", "<=", ">=", "<>", "(", ")", ";", ":", ",", ".", "+", "-", "*",
        "=", "<", ">", "&", "|", "!"]
_TOKEN_RE = None


def _strip_comments(s: str) -> str:
    s = re.sub(r"\(\*.*?\*\)", " ", s, flags=re.DOTALL)
    s = re.sub(r"//[^\n]*", " ", s)
    return s


# Discrete-time abstraction: 1 scan tick = 1 second. An IEC TIME literal (T#3s)
# is tokenized to its integer tick count so timers are finite-state checkable.
_TIME_UNIT_S = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}


def _time_to_ticks(lit: str) -> int:
    body = lit[2:].replace("_", "")  # drop 'T#'
    total = 0.0
    for num, unit in re.findall(r"([0-9]*\.?[0-9]+)\s*(ms|s|m|h|d)", body, re.I):
        total += float(num) * _TIME_UNIT_S[unit.lower()]
    return int(round(total))


@dataclass
class Tok:
    kind: str   # "kw" | "id" | "int" | "op"
    val: str


def tokenize(src: str) -> list[Tok]:
    s = _strip_comments(src)
    toks: list[Tok] = []
    i, n = 0, len(s)
    ops_sorted = sorted(_OPS, key=len, reverse=True)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in ("T", "t") and i + 1 < n and s[i + 1] == "#":   # TIME literal T#3s
            j = i + 2
            while j < n and (s[j].isalnum() or s[j] in "_."):
                j += 1
            toks.append(Tok("int", str(_time_to_ticks(s[i:j]))))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            up = word.upper()
            if up in _KEYWORDS:
                toks.append(Tok("kw", up))
            else:
                toks.append(Tok("id", word))
            i = j
            continue
        if c.isdigit():
            j = i + 1
            while j < n and s[j].isdigit():
                j += 1
            toks.append(Tok("int", s[i:j]))
            i = j
            continue
        for op in ops_sorted:
            if s.startswith(op, i):
                toks.append(Tok("op", op))
                i += len(op)
                break
        else:
            raise STSyntaxError(f"unexpected character {c!r} at offset {i}")
    return toks


# ---------------------------------------------------------------- parser
class _P:
    def __init__(self, toks: list[Tok]):
        self.t = toks
        self.i = 0

    def peek(self) -> Tok | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self) -> Tok:
        if self.i >= len(self.t):
            raise STSyntaxError("unexpected end of input")
        tok = self.t[self.i]
        self.i += 1
        return tok

    def accept(self, kind, val=None) -> Tok | None:
        tok = self.peek()
        if tok and tok.kind == kind and (val is None or tok.val == val):
            return self.next()
        return None

    def expect(self, kind, val=None) -> Tok:
        tok = self.accept(kind, val)
        if tok is None:
            got = self.peek()
            raise STSyntaxError(f"expected {val or kind}, got {got.val if got else 'EOF'}")
        return tok

    # ---- program / declarations
    def program(self) -> Program:
        self.expect("kw", "PROGRAM")
        name = self.expect("id").val
        decls = []
        while self.peek() and self.peek().kind == "kw" and self.peek().val.startswith("VAR"):
            decls += self.var_block()
        body = self.stmt_list({"END_PROGRAM"})
        self.expect("kw", "END_PROGRAM")
        return Program(name=name, decls=decls, body=body)

    def var_block(self) -> list[VarDecl]:
        kw = self.next().val  # VAR / VAR_INPUT / VAR_OUTPUT / VAR_IN_OUT
        const = self.accept("kw", "CONSTANT") is not None
        direction = {
            "VAR_INPUT": "input", "VAR_OUTPUT": "output",
            "VAR_IN_OUT": "input", "VAR": "internal",
        }.get(kw, "internal")
        decls = []
        while not self.accept("kw", "END_VAR"):
            name = self.expect("id").val
            self.expect("op", ":")
            typ = self.next()
            if typ.kind != "kw" or typ.val not in ("BOOL", "INT", "TON"):
                raise STSyntaxError(f"unsupported type {typ.val!r} (only BOOL, INT, TON)")
            init = None
            if self.accept("op", ":="):
                init = self._literal()
            self.expect("op", ";")
            decls.append(VarDecl(name=name, type=typ.val, direction=direction,
                                 const=const, init=init))
        return decls

    def _literal(self):
        tok = self.next()
        if tok.kind == "int":
            return int(tok.val)
        if tok.kind == "kw" and tok.val in ("TRUE", "FALSE"):
            return tok.val == "TRUE"
        if tok.kind == "op" and tok.val == "-":
            return -int(self.expect("int").val)
        raise STSyntaxError(f"expected literal, got {tok.val!r}")

    # ---- statements
    def stmt_list(self, stop_kw: set[str]) -> list:
        stmts = []
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok.kind == "kw" and tok.val in stop_kw:
                break
            stmts.append(self.statement())
        return stmts

    def statement(self):
        tok = self.peek()
        if tok.kind == "kw" and tok.val == "IF":
            return self.if_stmt()
        if tok.kind == "kw" and tok.val == "CASE":
            return self.case_stmt()
        if tok.kind == "id":
            name = self.next().val
            if self.accept("op", "("):
                return self.timer_call(name)
            self.expect("op", ":=")
            expr = self.expr()
            self.expect("op", ";")
            return Assign(target=name, expr=expr)
        raise STSyntaxError(f"unexpected token in statement: {tok.val!r}")

    def timer_call(self, inst: str) -> TimerCall:
        # '(' already consumed; parse named params IN:=..., PT:=... in any order
        params = {}
        while True:
            pname = self.expect("id").val.upper()
            self.expect("op", ":=")
            params[pname] = self.expr()
            if self.accept("op", ","):
                continue
            break
        self.expect("op", ")")
        self.accept("op", ";")
        if "IN" not in params or "PT" not in params:
            raise STSyntaxError(f"TON call {inst!r} requires IN and PT")
        return TimerCall(instance=inst, in_expr=params["IN"], pt=params["PT"])

    def case_stmt(self) -> Case:
        self.expect("kw", "CASE")
        selector = self.expr()
        self.expect("kw", "OF")
        branches = []
        while not (self.peek() and self.peek().kind == "kw"
                   and self.peek().val in ("END_CASE", "ELSE")):
            labels = {self._case_label()}
            while self.accept("op", ","):
                labels.add(self._case_label())
            self.expect("op", ":")
            body = self._case_branch_stmts()
            branches.append((labels, body))
        orelse = []
        if self.accept("kw", "ELSE"):
            orelse = self.stmt_list({"END_CASE"})
        self.expect("kw", "END_CASE")
        self.accept("op", ";")
        return Case(selector=selector, branches=branches, orelse=orelse)

    def _case_label(self) -> int:
        neg = self.accept("op", "-") is not None
        v = int(self.expect("int").val)
        return -v if neg else v

    def _at_case_label(self) -> bool:
        tok = self.peek()
        if tok is None:
            return False
        if tok.kind == "int":
            nxt = self.t[self.i + 1] if self.i + 1 < len(self.t) else None
            return nxt is not None and nxt.kind == "op" and nxt.val in (":", ",")
        if tok.kind == "op" and tok.val == "-":
            return (self.i + 2 < len(self.t) and self.t[self.i + 1].kind == "int"
                    and self.t[self.i + 2].kind == "op" and self.t[self.i + 2].val in (":", ","))
        return False

    def _case_branch_stmts(self) -> list:
        stmts = []
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok.kind == "kw" and tok.val in ("END_CASE", "ELSE"):
                break
            if self._at_case_label():
                break
            stmts.append(self.statement())
        return stmts

    def if_stmt(self) -> If:
        self.expect("kw", "IF")
        branches = []
        cond = self.expr()
        self.expect("kw", "THEN")
        body = self.stmt_list({"ELSIF", "ELSE", "END_IF"})
        branches.append((cond, body))
        while self.accept("kw", "ELSIF"):
            c = self.expr()
            self.expect("kw", "THEN")
            b = self.stmt_list({"ELSIF", "ELSE", "END_IF"})
            branches.append((c, b))
        orelse = []
        if self.accept("kw", "ELSE"):
            orelse = self.stmt_list({"END_IF"})
        self.expect("kw", "END_IF")
        self.accept("op", ";")  # optional trailing semicolon
        return If(branches=branches, orelse=orelse)

    # ---- expressions (precedence climbing)
    def expr(self):
        return self._or()

    def _or(self):
        node = self._and()
        while True:
            if self.accept("kw", "OR") or self.accept("op", "|"):
                node = Binary("OR", node, self._and())
            else:
                return node

    def _and(self):
        node = self._not()
        while True:
            if self.accept("kw", "AND") or self.accept("op", "&"):
                node = Binary("AND", node, self._not())
            else:
                return node

    def _not(self):
        if self.accept("kw", "NOT") or self.accept("op", "!"):
            return Unary("NOT", self._not())
        return self._cmp()

    def _cmp(self):
        node = self._add()
        tok = self.peek()
        if tok and tok.kind == "op" and tok.val in ("=", "<>", "<", "<=", ">", ">="):
            op = self.next().val
            return Binary(op, node, self._add())
        return node

    def _add(self):
        node = self._mul()
        while True:
            tok = self.peek()
            if tok and tok.kind == "op" and tok.val in ("+", "-"):
                op = self.next().val
                node = Binary(op, node, self._mul())
            else:
                return node

    def _mul(self):
        node = self._primary()
        while True:
            tok = self.peek()
            if tok and ((tok.kind == "op" and tok.val == "*") or (tok.kind == "kw" and tok.val == "MOD")):
                op = self.next().val
                node = Binary(op, node, self._primary())
            else:
                return node

    def _primary(self):
        tok = self.peek()
        if tok is None:
            raise STSyntaxError("unexpected end of expression")
        if self.accept("op", "("):
            node = self.expr()
            self.expect("op", ")")
            return node
        if self.accept("op", "-"):
            return Unary("-", self._primary())
        if tok.kind == "int":
            return Lit(int(self.next().val))
        if tok.kind == "kw" and tok.val in ("TRUE", "FALSE"):
            self.next()
            return Lit(tok.val == "TRUE")
        if tok.kind == "id":
            name = self.next().val
            if self.accept("op", "."):           # member access: T1.Q, T1.ET
                member = self.expect("id").val
                return Var(f"{name}.{member}")
            return Var(name)
        raise STSyntaxError(f"unexpected token in expression: {tok.val!r}")


def parse_program(src: str) -> Program:
    p = _P(tokenize(src))
    prog = p.program()
    if p.peek() is not None:
        raise STSyntaxError(f"trailing tokens after END_PROGRAM: {p.peek().val!r}")
    return prog
