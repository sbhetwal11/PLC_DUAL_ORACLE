"""Grammar-directed random ST program generator for the differential test.
Seeded and deterministic: Gen(s).program() always yields the same source."""
from __future__ import annotations
import random
import re


class Gen:
    def __init__(self, seed):
        self.r = random.Random(seed)
        self.seed = seed

    def program(self):
        r = self.r
        nbi = r.randint(2, 4); nii = r.randint(0, 2)
        nbo = r.randint(1, 3); nio = r.randint(0, 1)
        nbv = r.randint(0, 2); niv = r.randint(0, 1)
        nt = r.choice([0, 0, 1, 1, 2])
        self.bools = [f"BI{i}" for i in range(nbi)]
        self.ints = [f"NI{i}" for i in range(nii)]
        self.bout = [f"QO{i}" for i in range(nbo)]
        self.iout = [f"CO{i}" for i in range(nio)]
        self.bvar = [f"BV{i}" for i in range(nbv)]
        self.ivar = [f"NV{i}" for i in range(niv)]
        self.timers = [f"TM{i}" for i in range(nt)]
        d = [f"PROGRAM RP{self.seed}", "VAR_INPUT"]
        d += [f"    {v} : BOOL;" for v in self.bools]
        d += [f"    {v} : INT;" for v in self.ints]
        d += ["END_VAR", "VAR_OUTPUT"]
        d += [f"    {v} : BOOL;" for v in self.bout]
        d += [f"    {v} : INT;" for v in self.iout]
        d += ["END_VAR"]
        if self.bvar or self.ivar or self.timers:
            d.append("VAR")
            d += [f"    {v} : BOOL := {r.choice(['TRUE','FALSE'])};" for v in self.bvar]
            d += [f"    {v} : INT := {r.randint(0, 3)};" for v in self.ivar]
            d += [f"    {t} : TON;" for t in self.timers]
            d.append("END_VAR")
        body = []
        for t in self.timers:   # every timer called exactly once per scan
            body.append(f"{t}(IN := {self.bexpr(2)}, PT := T#{r.randint(1, 4)}s);")
        for _ in range(r.randint(3, 8)):
            body.append(self.stmt())
        assigned = " ".join(body)
        for v in self.bout:
            if not re.search(rf"\b{v}\s*:=", assigned):
                body.append(f"{v} := {self.bexpr(1)};")
        for v in self.iout:
            if not re.search(rf"\b{v}\s*:=", assigned):
                body.append(f"{v} := {self.iassign_rhs()};")
        return "\n".join(d) + "\n" + "\n".join(body) + "\nEND_PROGRAM\n"

    # ---- expressions
    def batom(self):
        r = self.r
        pool = self.bools + self.bvar + self.bout + [f"{t}.Q" for t in self.timers]
        c = r.random()
        if c < 0.55 and pool:
            return r.choice(pool)
        if c < 0.8 and (self.ints + self.ivar + self.iout):
            v = r.choice(self.ints + self.ivar + self.iout)
            op = r.choice(["=", "<>", "<", "<=", ">", ">="])
            return f"({v} {op} {r.randint(0, 5)})"
        return r.choice(["TRUE", "FALSE"])

    def bexpr(self, depth):
        r = self.r
        if depth <= 0 or r.random() < 0.35:
            a = self.batom()
            return f"NOT {a}" if r.random() < 0.25 else a
        op = r.choice(["AND", "OR"])
        return f"({self.bexpr(depth - 1)} {op} {self.bexpr(depth - 1)})"

    def iatom(self):
        r = self.r
        pool = self.ints + self.ivar + self.iout
        return r.choice(pool) if pool and r.random() < 0.7 else str(r.randint(0, 5))

    def iassign_rhs(self):
        # always non-negative and MOD-bounded so Python/C MOD semantics coincide
        r = self.r
        k = r.randint(2, 6)
        c = r.random()
        if c < 0.4:
            e = f"{self.iatom()} + {r.randint(0, 3)}"
        elif c < 0.7:
            e = f"{self.iatom()} + {self.iatom()}"
        else:
            e = f"{self.iatom()} * {r.randint(1, 3)}"
        return f"({e}) MOD {k}"

    # ---- statements
    def assign(self):
        r = self.r
        ipool = self.iout + self.ivar
        if ipool and r.random() < 0.35:
            return f"{r.choice(ipool)} := {self.iassign_rhs()};"
        return f"{r.choice(self.bout + self.bvar) if (self.bout + self.bvar) else self.bout[0]} := {self.bexpr(2)};"

    def stmt(self, depth=1):
        r = self.r
        c = r.random()
        if c < 0.45 or depth <= 0:
            return self.assign()
        if c < 0.8:
            s = [f"IF {self.bexpr(2)} THEN", f"    {self.assign()}"]
            for _ in range(r.randint(0, 2)):
                s += [f"ELSIF {self.bexpr(1)} THEN", f"    {self.assign()}"]
            if r.random() < 0.6:
                s += ["ELSE", f"    {self.assign()}"]
            s.append("END_IF;")
            return "\n".join(s)
        ipool = self.ints + self.ivar + self.iout
        if not ipool:
            return self.assign()
        sel = r.choice(ipool)
        labels = r.sample(range(0, 6), r.randint(2, 3))
        s = [f"CASE {sel} OF"]
        for lab in labels:
            s += [f"{lab}: {self.assign()}"]
        if r.random() < 0.7:
            s += ["ELSE", f"    {self.assign()}"]
        s.append("END_CASE;")
        return "\n".join(s)
