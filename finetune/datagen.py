"""Procedural task-family generators for SFT data.

Each generator yields (meta_dict, reference_st). Families are parameterised
generalisations of patterns we know verify, with lexical variation (output/program
names) so the model does not overfit a single template. All instances are DISJOINT
from the 22 eval tasks (different ids, names, parameters). build_sft.py verifies
every reference with the dual oracle and keeps only verified pairs.
"""
from __future__ import annotations

# output-name pool (must not collide case-insensitively with the program name)
ONAMES = ["Motor", "Drive", "Pump", "Fan", "Mixer", "Blower", "Spindle", "Auger"]


def _prog(family: str, tag) -> str:
    return f"p_{family}_{tag}"


def multi_guard(n: int, out: str):
    guards = [f"G{i}" for i in range(1, n + 1)]
    interface = [
        {"name": "StartPB", "type": "BOOL", "direction": "input", "description": "Start"},
        {"name": "StopPB", "type": "BOOL", "direction": "input", "description": "Stop"},
    ]
    for g in guards:
        interface.append({"name": g, "type": "BOOL", "direction": "input",
                          "description": f"Guard {g} closed (TRUE=safe)"})
    interface.append({"name": out, "type": "BOOL", "direction": "output",
                      "description": "Actuator"})
    props = [{"id": f"PG{i+1}", "kind": "safety", "severity": "critical",
              "nl": f"Never runs while guard {g} is open.",
              "ltl": f"G(!{g} -> !{out})"} for i, g in enumerate(guards)]
    props.append({"id": "PStop", "kind": "safety", "severity": "high",
                  "nl": "Off when stop is pressed.", "ltl": f"G(StopPB -> !{out})"})
    prog = _prog("mguard", f"{n}_{out.lower()}")
    meta = {"id": f"GEN_mguard_{n}_{out}", "title": f"{n}-guard machine ({out})",
            "difficulty": "easy" if n <= 2 else "medium", "domain": "machine safety",
            "nl_spec": (f"A machine ({out}) latches on with StartPB and off with StopPB. "
                        f"It may run only while ALL guards {', '.join(guards)} are closed "
                        f"(TRUE); any open guard stops it and blocks starting. Write an "
                        f"IEC 61131-3 ST PROGRAM named {prog} with output {out}."),
            "interface": interface, "safety_properties": props, "scenarios": []}
    gd = "\n".join(f"    {g} : BOOL;" for g in guards)
    gor = " OR ".join(f"(NOT {g})" for g in guards)
    gand = " AND ".join(["StartPB"] + guards)
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    StartPB : BOOL;\n    StopPB  : BOOL;\n{gd}\n"
          f"END_VAR\nVAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\n\n"
          f"IF StopPB OR {gor} THEN\n    {out} := FALSE;\n"
          f"ELSIF {gand} THEN\n    {out} := TRUE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def estop_bus(n: int, out: str):
    es = [f"E{i}" for i in range(1, n + 1)]
    interface = [
        {"name": "Start", "type": "BOOL", "direction": "input", "description": "Start"},
        {"name": "Stop", "type": "BOOL", "direction": "input", "description": "Stop"},
    ]
    for e in es:
        interface.append({"name": e, "type": "BOOL", "direction": "input",
                          "description": f"E-stop {e} (NC: TRUE=healthy)"})
    interface.append({"name": out, "type": "BOOL", "direction": "output",
                      "description": "Actuator"})
    props = [{"id": f"PE{i+1}", "kind": "safety", "severity": "critical",
              "nl": f"E-stop {e} de-energises the output.",
              "ltl": f"G(!{e} -> !{out})"} for i, e in enumerate(es)]
    props.append({"id": "PStop", "kind": "safety", "severity": "high",
                  "nl": "Stop de-energises the output.", "ltl": f"G(Stop -> !{out})"})
    prog = _prog("estop", f"{n}_{out.lower()}")
    meta = {"id": f"GEN_estop_{n}_{out}", "title": f"{n}-channel e-stop bus ({out})",
            "difficulty": "easy" if n <= 2 else "medium", "domain": "machine safety",
            "nl_spec": (f"An actuator ({out}) latches on with Start and off with Stop. "
                        f"Any of the normally-closed e-stops {', '.join(es)} (TRUE=healthy, "
                        f"FALSE=activated) must immediately de-energise it and block starting. "
                        f"Write an IEC 61131-3 ST PROGRAM named {prog} with output {out}."),
            "interface": interface, "safety_properties": props, "scenarios": []}
    ed = "\n".join(f"    {e} : BOOL;" for e in es)
    eor = " OR ".join(f"(NOT {e})" for e in es)
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    Start : BOOL;\n    Stop  : BOOL;\n{ed}\n"
          f"END_VAR\nVAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\n\n"
          f"IF {eor} OR Stop THEN\n    {out} := FALSE;\n"
          f"ELSIF Start THEN\n    {out} := TRUE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def ondelay(pt: int, out: str):
    prog = _prog("ondly", f"{pt}_{out.lower()}")
    meta = {"id": f"GEN_ondelay_{pt}_{out}", "title": f"On-delay start ({out}, {pt}s)",
            "difficulty": "medium", "domain": "motor control",
            "nl_spec": (f"An actuator ({out}) energises only after StartCmd has been held "
                        f"(with EStop healthy) for T#{pt}s, and de-energises when StartCmd "
                        f"drops. EStop (NC: TRUE=healthy) immediately stops it. Use a TON "
                        f"timer. Write an IEC 61131-3 ST PROGRAM named {prog} with output {out}."),
            "interface": [
                {"name": "StartCmd", "type": "BOOL", "direction": "input", "description": "Start"},
                {"name": "EStop", "type": "BOOL", "direction": "input", "description": "E-stop NC"},
                {"name": out, "type": "BOOL", "direction": "output", "description": "Actuator"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": "E-stop de-energises.", "ltl": f"G(!EStop -> !{out})"},
                {"id": "P2", "kind": "safety", "severity": "high",
                 "nl": "Runs only while commanded.", "ltl": f"G({out} -> StartCmd)"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    StartCmd : BOOL;\n    EStop : BOOL;\nEND_VAR\n"
          f"VAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\nVAR\n    T1 : TON;\nEND_VAR\n\n"
          f"T1(IN := StartCmd AND EStop, PT := T#{pt}s);\n\n"
          f"IF NOT EStop THEN\n    {out} := FALSE;\n"
          f"ELSIF T1.Q THEN\n    {out} := TRUE;\nELSE\n    {out} := FALSE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def override_cutout(out: str, trip: str):
    prog = _prog("ovr", out.lower())
    meta = {"id": f"GEN_override_{out}_{trip}", "title": f"Override cutout ({out}/{trip})",
            "difficulty": "easy", "domain": "process control",
            "nl_spec": (f"An actuator ({out}) is energised on Demand when Enable is true, but "
                        f"{trip} (TRUE) is a hard override that forces it off. Non-latching. "
                        f"Write an IEC 61131-3 ST PROGRAM named {prog} with output {out}."),
            "interface": [
                {"name": "Demand", "type": "BOOL", "direction": "input", "description": "Demand"},
                {"name": "Enable", "type": "BOOL", "direction": "input", "description": "Enable"},
                {"name": trip, "type": "BOOL", "direction": "input", "description": "Trip override"},
                {"name": out, "type": "BOOL", "direction": "output", "description": "Actuator"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": f"{trip} forces off.", "ltl": f"G({trip} -> !{out})"},
                {"id": "P2", "kind": "safety", "severity": "high",
                 "nl": "On only when enabled.", "ltl": f"G({out} -> Enable)"},
                {"id": "P3", "kind": "safety", "severity": "medium",
                 "nl": "On only on demand.", "ltl": f"G({out} -> Demand)"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    Demand : BOOL;\n    Enable : BOOL;\n    {trip} : BOOL;\n"
          f"END_VAR\nVAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\n\n"
          f"IF {trip} THEN\n    {out} := FALSE;\n"
          f"ELSIF Demand AND Enable THEN\n    {out} := TRUE;\nELSE\n    {out} := FALSE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def bounded_counter(cap: int, out: str):
    prog = _prog("cnt", f"{cap}_{out.lower()}")
    meta = {"id": f"GEN_counter_{cap}_{out}", "title": f"Bounded counter to {cap} ({out})",
            "difficulty": "medium", "domain": "process control",
            "nl_spec": (f"Count rising edges of Pulse up to {cap} (never exceed it); assert "
                        f"{out} when the count reaches {cap}. Reset clears the count. Use an "
                        f"internal INT Count (0..{cap}) and a PrevPulse edge flag. Write an "
                        f"IEC 61131-3 ST PROGRAM named {prog} with output {out}."),
            "interface": [
                {"name": "Pulse", "type": "BOOL", "direction": "input", "description": "Count pulse"},
                {"name": "Reset", "type": "BOOL", "direction": "input", "description": "Clear"},
                {"name": out, "type": "BOOL", "direction": "output", "description": "Target reached"},
                {"name": "Count", "type": "INT", "direction": "internal",
                 "description": "Count", "range": [0, cap]},
                {"name": "PrevPulse", "type": "BOOL", "direction": "internal",
                 "description": "Edge flag"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": "Count never exceeds the cap.", "ltl": f"G(Count <= {cap})"},
                {"id": "P2", "kind": "safety", "severity": "high",
                 "nl": "Flag only at target.", "ltl": f"G({out} -> Count >= {cap})"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    Pulse : BOOL;\n    Reset : BOOL;\nEND_VAR\n"
          f"VAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\nVAR\n    Count : INT;\n    PrevPulse : BOOL;\nEND_VAR\n"
          f"VAR CONSTANT\n    CAP : INT := {cap};\nEND_VAR\n\n"
          f"IF Reset THEN\n    Count := 0;\n"
          f"ELSIF Pulse AND NOT PrevPulse AND Count < CAP THEN\n    Count := Count + 1;\nEND_IF;\n\n"
          f"PrevPulse := Pulse;\n{out} := Count >= CAP;\n\nEND_PROGRAM\n")
    return meta, st


def exclusive_two(a: str, b: str):
    prog = _prog("excl", f"{a.lower()}_{b.lower()}")
    meta = {"id": f"GEN_excl_{a}_{b}", "title": f"Mutual exclusion ({a}/{b})",
            "difficulty": "easy", "domain": "safety interlock",
            "nl_spec": (f"Two outputs {a} and {b} must never be on together. {a} turns on with "
                        f"ReqA (priority); {b} turns on with ReqB only if {a} is off. Write an "
                        f"IEC 61131-3 ST PROGRAM named {prog} with outputs {a} and {b}."),
            "interface": [
                {"name": "ReqA", "type": "BOOL", "direction": "input", "description": "Request A"},
                {"name": "ReqB", "type": "BOOL", "direction": "input", "description": "Request B"},
                {"name": a, "type": "BOOL", "direction": "output", "description": "Output A"},
                {"name": b, "type": "BOOL", "direction": "output", "description": "Output B"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": "Never both on.", "ltl": f"G(!({a} & {b}))"},
                {"id": "P2", "kind": "safety", "severity": "high",
                 "nl": "A only on request.", "ltl": f"G({a} -> ReqA)"},
                {"id": "P3", "kind": "safety", "severity": "high",
                 "nl": "B only on request.", "ltl": f"G({b} -> ReqB)"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    ReqA : BOOL;\n    ReqB : BOOL;\nEND_VAR\n"
          f"VAR_OUTPUT\n    {a} : BOOL;\n    {b} : BOOL;\nEND_VAR\n\n"
          f"IF ReqA THEN\n    {a} := TRUE;\nELSE\n    {a} := FALSE;\nEND_IF;\n\n"
          f"IF ReqB AND NOT {a} THEN\n    {b} := TRUE;\nELSE\n    {b} := FALSE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def hysteresis(high: int, low: int, out: str = "Actuator"):
    prog = _prog("hyst", f"{low}_{high}")
    meta = {"id": f"GEN_hyst_{low}_{high}", "title": f"Hysteresis (LOW={low},HIGH={high})",
            "difficulty": "easy", "domain": "process control",
            "nl_spec": (f"Two-point control on Level (0..100): turn {out} ON at/below {low}, OFF "
                        f"at/above {high}, hold otherwise. SAFETY: off whenever Level>={high}. "
                        f"Write an IEC 61131-3 ST PROGRAM named {prog} with output {out}."),
            "interface": [
                {"name": "Level", "type": "INT", "direction": "input",
                 "description": "Level", "range": [0, 100]},
                {"name": out, "type": "BOOL", "direction": "output", "description": "Actuator"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": f"Off at/above {high}.", "ltl": f"G(Level >= {high} -> !{out})"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    Level : INT;\nEND_VAR\nVAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\n"
          f"VAR CONSTANT\n    HI : INT := {high};\n    LO : INT := {low};\nEND_VAR\n\n"
          f"IF Level >= HI THEN\n    {out} := FALSE;\n"
          f"ELSIF Level <= LO THEN\n    {out} := TRUE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


# ---------------------------------------------------------------------------
# HARDER held-in families (Phase-3 v2). Each composes constructs already proven
# to verify (latched IF/ELSIF, TON, bounded INT, mutual exclusion) into tasks
# with more inputs / outputs / properties, so they sit above the easy tier and
# give SFT genuinely harder in-distribution examples. build_sft verifies every
# one with the dual oracle and drops any that do not.
# ---------------------------------------------------------------------------

def safety_chain(ne: int, ng: int, out: str):
    """Start/stop latch gated by ne normally-closed e-stops AND ng guards."""
    es = [f"E{i}" for i in range(1, ne + 1)]
    gs = [f"G{i}" for i in range(1, ng + 1)]
    prog = _prog("chain", f"{ne}e{ng}g_{out.lower()}")
    interface = [{"name": "Start", "type": "BOOL", "direction": "input", "description": "Start"},
                 {"name": "Stop", "type": "BOOL", "direction": "input", "description": "Stop"}]
    for e in es:
        interface.append({"name": e, "type": "BOOL", "direction": "input",
                          "description": f"E-stop {e} (NC: TRUE=healthy)"})
    for g in gs:
        interface.append({"name": g, "type": "BOOL", "direction": "input",
                          "description": f"Guard {g} (TRUE=closed)"})
    interface.append({"name": out, "type": "BOOL", "direction": "output", "description": "Actuator"})
    props = []
    for i, e in enumerate(es):
        props.append({"id": f"PE{i+1}", "kind": "safety", "severity": "critical",
                      "nl": f"E-stop {e} de-energises.", "ltl": f"G(!{e} -> !{out})"})
    for i, g in enumerate(gs):
        props.append({"id": f"PG{i+1}", "kind": "safety", "severity": "critical",
                      "nl": f"Open guard {g} de-energises.", "ltl": f"G(!{g} -> !{out})"})
    props.append({"id": "PStop", "kind": "safety", "severity": "high",
                  "nl": "Stop de-energises.", "ltl": f"G(Stop -> !{out})"})
    meta = {"id": f"GEN_chain_{ne}e{ng}g_{out}", "title": f"Safety chain {ne}E/{ng}G ({out})",
            "difficulty": "medium", "domain": "machine safety",
            "nl_spec": (f"An actuator ({out}) latches on with Start and off with Stop. It may run "
                        f"only while ALL e-stops {', '.join(es)} are healthy (TRUE) AND all guards "
                        f"{', '.join(gs)} are closed (TRUE); any unhealthy e-stop or open guard "
                        f"immediately de-energises it and blocks starting. Write an IEC 61131-3 ST "
                        f"PROGRAM named {prog} with output {out}."),
            "interface": interface, "safety_properties": props, "scenarios": []}
    decl = "\n".join(f"    {x} : BOOL;" for x in es + gs)
    bad = " OR ".join([f"(NOT {x})" for x in es + gs] + ["Stop"])
    healthy = " AND ".join(["Start"] + es + gs)
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    Start : BOOL;\n    Stop  : BOOL;\n{decl}\nEND_VAR\n"
          f"VAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\n\n"
          f"IF {bad} THEN\n    {out} := FALSE;\n"
          f"ELSIF {healthy} THEN\n    {out} := TRUE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def bounded_updown(cap: int, out: str):
    """Up/down counter clamped to [0, cap]; Full asserted at the cap."""
    prog = _prog("udn", f"{cap}_{out.lower()}")
    meta = {"id": f"GEN_updown_{cap}_{out}", "title": f"Up/down counter 0..{cap} ({out})",
            "difficulty": "medium", "domain": "process control",
            "nl_spec": (f"Maintain an internal INT Count in 0..{cap}. A rising edge of Inc adds 1 "
                        f"(never above {cap}); a rising edge of Dec subtracts 1 (never below 0). "
                        f"Reset clears it. Assert {out} when Count reaches {cap}. Use PrevInc/PrevDec "
                        f"edge flags. Write an IEC 61131-3 ST PROGRAM named {prog} with output {out}."),
            "interface": [
                {"name": "Inc", "type": "BOOL", "direction": "input", "description": "Count up"},
                {"name": "Dec", "type": "BOOL", "direction": "input", "description": "Count down"},
                {"name": "Reset", "type": "BOOL", "direction": "input", "description": "Clear"},
                {"name": out, "type": "BOOL", "direction": "output", "description": "At cap"},
                {"name": "Count", "type": "INT", "direction": "internal", "description": "Count",
                 "range": [0, cap]},
                {"name": "PrevInc", "type": "BOOL", "direction": "internal", "description": "Edge"},
                {"name": "PrevDec", "type": "BOOL", "direction": "internal", "description": "Edge"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": "Count never exceeds the cap.", "ltl": f"G(Count <= {cap})"},
                {"id": "P2", "kind": "safety", "severity": "critical",
                 "nl": "Count never goes negative.", "ltl": "G(Count >= 0)"},
                {"id": "P3", "kind": "safety", "severity": "high",
                 "nl": "Full only at the cap.", "ltl": f"G({out} -> Count >= {cap})"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    Inc : BOOL;\n    Dec : BOOL;\n    Reset : BOOL;\nEND_VAR\n"
          f"VAR_OUTPUT\n    {out} : BOOL;\nEND_VAR\n"
          f"VAR\n    Count : INT;\n    PrevInc : BOOL;\n    PrevDec : BOOL;\nEND_VAR\n"
          f"VAR CONSTANT\n    CAP : INT := {cap};\nEND_VAR\n\n"
          f"IF Reset THEN\n    Count := 0;\n"
          f"ELSIF Inc AND NOT PrevInc AND Count < CAP THEN\n    Count := Count + 1;\n"
          f"ELSIF Dec AND NOT PrevDec AND Count > 0 THEN\n    Count := Count - 1;\nEND_IF;\n\n"
          f"PrevInc := Inc;\nPrevDec := Dec;\n{out} := Count >= CAP;\n\nEND_PROGRAM\n")
    return meta, st


def ordered_pair(a: str, b: str):
    """Two latched stages: B may run only while A runs; Stop/EStop drop both."""
    prog = _prog("ord", f"{a.lower()}_{b.lower()}")
    meta = {"id": f"GEN_ordered_{a}_{b}", "title": f"Ordered start ({a} before {b})",
            "difficulty": "medium", "domain": "sequencing",
            "nl_spec": (f"Two stages {a} and {b}. {a} latches on with StartA; {b} latches on with "
                        f"StartB but ONLY while {a} is already running. Stop or an unhealthy EStop "
                        f"(NC: TRUE=healthy) drops both immediately, and {b} must drop whenever {a} "
                        f"is off. Write an IEC 61131-3 ST PROGRAM named {prog} with outputs {a},{b}."),
            "interface": [
                {"name": "StartA", "type": "BOOL", "direction": "input", "description": "Start A"},
                {"name": "StartB", "type": "BOOL", "direction": "input", "description": "Start B"},
                {"name": "Stop", "type": "BOOL", "direction": "input", "description": "Stop"},
                {"name": "EStop", "type": "BOOL", "direction": "input", "description": "E-stop NC"},
                {"name": a, "type": "BOOL", "direction": "output", "description": "Stage A"},
                {"name": b, "type": "BOOL", "direction": "output", "description": "Stage B"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": f"{b} implies {a}.", "ltl": f"G({b} -> {a})"},
                {"id": "P2", "kind": "safety", "severity": "critical",
                 "nl": "E-stop drops both.", "ltl": f"G(!EStop -> (!{a} & !{b}))"},
                {"id": "P3", "kind": "safety", "severity": "high",
                 "nl": "Stop drops both.", "ltl": f"G(Stop -> (!{a} & !{b}))"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    StartA : BOOL;\n    StartB : BOOL;\n    Stop : BOOL;\n"
          f"    EStop : BOOL;\nEND_VAR\nVAR_OUTPUT\n    {a} : BOOL;\n    {b} : BOOL;\nEND_VAR\n\n"
          f"IF Stop OR (NOT EStop) THEN\n    {a} := FALSE;\n    {b} := FALSE;\n"
          f"ELSE\n    IF StartA THEN\n        {a} := TRUE;\n    END_IF;\n"
          f"    IF StartB AND {a} THEN\n        {b} := TRUE;\n    END_IF;\n"
          f"    IF NOT {a} THEN\n        {b} := FALSE;\n    END_IF;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def two_speed(out: str):
    """Mutually-exclusive Slow/Fast drive gated by an e-stop; Fast needs enable."""
    slow, fast = f"{out}Slow", f"{out}Fast"
    prog = _prog("spd", out.lower())
    meta = {"id": f"GEN_twospeed_{out}", "title": f"Two-speed drive ({out})",
            "difficulty": "medium", "domain": "motor control",
            "nl_spec": (f"A drive has two outputs {slow} and {fast} that must NEVER be on together. "
                        f"ReqSlow energises {slow}; ReqFast energises {fast} only if FastEnable is "
                        f"true and ReqSlow is not. An unhealthy EStop (NC: TRUE=healthy) forces both "
                        f"off. Write an IEC 61131-3 ST PROGRAM named {prog} with outputs {slow},{fast}."),
            "interface": [
                {"name": "ReqSlow", "type": "BOOL", "direction": "input", "description": "Request slow"},
                {"name": "ReqFast", "type": "BOOL", "direction": "input", "description": "Request fast"},
                {"name": "FastEnable", "type": "BOOL", "direction": "input", "description": "Fast permit"},
                {"name": "EStop", "type": "BOOL", "direction": "input", "description": "E-stop NC"},
                {"name": slow, "type": "BOOL", "direction": "output", "description": "Slow"},
                {"name": fast, "type": "BOOL", "direction": "output", "description": "Fast"}],
            "safety_properties": [
                {"id": "P1", "kind": "safety", "severity": "critical",
                 "nl": "Never both speeds.", "ltl": f"G(!({slow} & {fast}))"},
                {"id": "P2", "kind": "safety", "severity": "critical",
                 "nl": "E-stop forces off.", "ltl": f"G(!EStop -> (!{slow} & !{fast}))"},
                {"id": "P3", "kind": "safety", "severity": "high",
                 "nl": "Fast needs enable.", "ltl": f"G({fast} -> FastEnable)"}],
            "scenarios": []}
    st = (f"PROGRAM {prog}\nVAR_INPUT\n    ReqSlow : BOOL;\n    ReqFast : BOOL;\n    FastEnable : BOOL;\n"
          f"    EStop : BOOL;\nEND_VAR\nVAR_OUTPUT\n    {slow} : BOOL;\n    {fast} : BOOL;\nEND_VAR\n\n"
          f"IF NOT EStop THEN\n    {slow} := FALSE;\n    {fast} := FALSE;\n"
          f"ELSIF ReqSlow THEN\n    {slow} := TRUE;\n    {fast} := FALSE;\n"
          f"ELSIF ReqFast AND FastEnable THEN\n    {slow} := FALSE;\n    {fast} := TRUE;\n"
          f"ELSE\n    {slow} := FALSE;\n    {fast} := FALSE;\nEND_IF;\n\nEND_PROGRAM\n")
    return meta, st


def generate_hard():
    """Yield (meta, st) for the harder v2 families (~40 instances)."""
    outs = ["Motor", "Drive", "Pump", "Conveyor", "Mixer", "Hoist"]
    for out in outs:
        for ne, ng in ((1, 2), (2, 1), (2, 2), (3, 2)):
            yield safety_chain(ne, ng, out)
        yield two_speed(out)
    for cap in (2, 3, 4, 5, 6):
        for out in ("Bay", "Slot", "Buffer"):
            yield bounded_updown(cap, out)
    for a, b in (("Feed", "Mix"), ("Pump", "Heat"), ("Conv1", "Conv2"),
                 ("Lube", "Spindle"), ("Charge", "Run")):
        yield ordered_pair(a, b)


def generate_all():
    """Yield (meta, st) over parameter + name grids (~150+ instances)."""
    for i, out in enumerate(ONAMES):
        for n in (1, 2, 3, 4):
            yield multi_guard(n, out)
            yield estop_bus(n, out)
        for pt in (1, 2, 3, 4):
            yield ondelay(pt, out)
        for cap in (2, 3, 4, 5):
            yield bounded_counter(cap, out)
        yield override_cutout(out, "OverTemp")
        yield override_cutout(out, "Fault")
    for high in (70, 80, 90):
        for low in (5, 10, 20):
            if low < high - 10:
                yield hysteresis(high, low)
    for a, b in (("DoorA", "DoorB"), ("ValveX", "ValveY"), ("Heat", "Cool"),
                 ("FwdK", "RevK"), ("StarK", "DeltaK")):
        yield exclusive_two(a, b)
