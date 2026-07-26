"""Functional-scenario synthesis for the procedural training families.

The 22-task benchmark ships execution scenarios, but the datagen families
(finetune/datagen.py) do not. DeepReview B1/B4 require a FUNCTIONAL signal in
both the SFT filter and the RL reward, otherwise the inert all-off controller
scores near-maximally. This module synthesises positive-activation scenarios for
each family and, crucially, keeps only scenarios that

  (1) the family's own verified reference PASSES, and
  (2) an all-off controller FAILS

so every kept scenario is correct-by-construction and genuinely discriminates a
working controller from doing nothing. Timer families are validated the same way,
so any off-by-one in the abstract TON timing is filtered out automatically.
"""
from __future__ import annotations

import re

from plcbench.schema import Task
from plcbench.st.interp import check_scenarios_src
from plcbench.schema import Scenario


def _inputs_by_dir(meta, direction):
    return [v["name"] for v in meta["interface"] if v["direction"] == direction]


def _outputs(meta):
    return _inputs_by_dir(meta, "output")


def _cap_from_range(meta, name):
    for v in meta["interface"]:
        if v["name"] == name and v.get("range"):
            return int(v["range"][1])
    return None


def _candidates(meta):
    """Family-specific candidate scenarios (best effort; validated downstream)."""
    fid = meta["id"]
    outs = _outputs(meta)
    ins = _inputs_by_dir(meta, "input")
    S = []

    def step(inp, exp):
        return {"inputs": inp, "expect": exp}

    if fid.startswith("GEN_mguard_"):
        guards = [x for x in ins if re.fullmatch(r"G\d+", x)]
        out = outs[0]
        on = {"StartPB": True, "StopPB": False, **{g: True for g in guards}}
        S.append({"id": "S_on", "description": "activate",
                  "steps": [step(on, {out: True})]})
        S.append({"id": "S_stop", "description": "stop drops",
                  "steps": [step(on, {out: True}),
                            step({**on, "StopPB": True}, {out: False})]})
        if guards:
            S.append({"id": "S_guard", "description": "open guard drops",
                      "steps": [step(on, {out: True}),
                                step({**on, guards[0]: False}, {out: False})]})

    elif fid.startswith("GEN_estop_"):
        es = [x for x in ins if re.fullmatch(r"E\d+", x)]
        out = outs[0]
        on = {"Start": True, "Stop": False, **{e: True for e in es}}
        S.append({"id": "S_on", "description": "activate",
                  "steps": [step(on, {out: True})]})
        S.append({"id": "S_stop", "description": "stop drops",
                  "steps": [step(on, {out: True}),
                            step({**on, "Stop": True}, {out: False})]})
        if es:
            S.append({"id": "S_estop", "description": "estop drops",
                      "steps": [step(on, {out: True}),
                                step({**on, es[0]: False}, {out: False})]})

    elif fid.startswith("GEN_ondelay_"):
        pt = int(fid.split("_")[2])
        out = outs[0]
        hold = {"StartCmd": True, "EStop": True}
        # hold long enough for the abstract TON to elapse, then expect ON
        steps = [step(hold, {}) for _ in range(pt + 2)]
        steps[-1] = step(hold, {out: True})
        S.append({"id": "S_delay_on", "description": "energises after delay",
                  "steps": steps})
        S.append({"id": "S_estop", "description": "estop keeps off",
                  "steps": [step({"StartCmd": True, "EStop": False}, {out: False})]})

    elif fid.startswith("GEN_override_"):
        out = outs[0]
        trip = [x for x in ins if x not in ("Demand", "Enable")][0]
        on = {"Demand": True, "Enable": True, trip: False}
        S.append({"id": "S_on", "description": "activate",
                  "steps": [step(on, {out: True})]})
        S.append({"id": "S_trip", "description": "trip forces off",
                  "steps": [step(on, {out: True}),
                            step({**on, trip: True}, {out: False})]})

    elif fid.startswith("GEN_counter_"):
        cap = int(fid.split("_")[2])
        out = outs[0]
        steps = [step({"Pulse": False, "Reset": True}, {out: False})]
        for _ in range(cap):                       # cap rising edges
            steps.append(step({"Pulse": True, "Reset": False}, {}))
            steps.append(step({"Pulse": False, "Reset": False}, {}))
        steps[-1]["expect"] = {out: True}
        S.append({"id": "S_count", "description": "reaches target", "steps": steps})

    elif fid.startswith("GEN_updown_"):
        cap = int(fid.split("_")[2])
        out = outs[0]
        steps = [step({"Inc": False, "Dec": False, "Reset": True}, {out: False})]
        for _ in range(cap):
            steps.append(step({"Inc": True, "Dec": False, "Reset": False}, {}))
            steps.append(step({"Inc": False, "Dec": False, "Reset": False}, {}))
        steps[-1]["expect"] = {out: True}
        S.append({"id": "S_up", "description": "counts up to cap", "steps": steps})

    elif fid.startswith("GEN_excl_"):
        a, b = outs[0], outs[1]
        S.append({"id": "S_a", "description": "A on request",
                  "steps": [step({"ReqA": True, "ReqB": False}, {a: True, b: False})]})
        S.append({"id": "S_b", "description": "B on request when A off",
                  "steps": [step({"ReqA": False, "ReqB": True}, {a: False, b: True})]})

    elif fid.startswith("GEN_hyst_"):
        low = int(fid.split("_")[2]); high = int(fid.split("_")[3])
        out = outs[0]
        S.append({"id": "S_low", "description": "on at/below low",
                  "steps": [step({"Level": low}, {out: True})]})
        S.append({"id": "S_high", "description": "off at/above high",
                  "steps": [step({"Level": low}, {out: True}),
                            step({"Level": high}, {out: False})]})

    elif fid.startswith("GEN_chain_"):
        es = [x for x in ins if re.fullmatch(r"E\d+", x)]
        gs = [x for x in ins if re.fullmatch(r"G\d+", x)]
        out = outs[0]
        on = {"Start": True, "Stop": False, **{e: True for e in es},
              **{g: True for g in gs}}
        S.append({"id": "S_on", "description": "activate",
                  "steps": [step(on, {out: True})]})
        if es:
            S.append({"id": "S_estop", "description": "estop drops",
                      "steps": [step(on, {out: True}),
                                step({**on, es[0]: False}, {out: False})]})
        if gs:
            S.append({"id": "S_guard", "description": "open guard drops",
                      "steps": [step(on, {out: True}),
                                step({**on, gs[0]: False}, {out: False})]})

    elif fid.startswith("GEN_ordered_"):
        a, b = outs[0], outs[1]
        base = {"Stop": False, "EStop": True}
        S.append({"id": "S_seq", "description": "A then B",
                  "steps": [step({**base, "StartA": True, "StartB": False}, {a: True}),
                            step({**base, "StartA": True, "StartB": True},
                                 {a: True, b: True})]})
        S.append({"id": "S_estop", "description": "estop drops both",
                  "steps": [step({**base, "StartA": True, "StartB": True}, {}),
                            step({"Stop": False, "EStop": False, "StartA": True,
                                  "StartB": True}, {a: False, b: False})]})

    elif fid.startswith("GEN_twospeed_"):
        slow, fast = outs[0], outs[1]
        S.append({"id": "S_slow", "description": "slow on request",
                  "steps": [step({"EStop": True, "ReqSlow": True, "ReqFast": False,
                                  "FastEnable": False}, {slow: True, fast: False})]})
        S.append({"id": "S_fast", "description": "fast when enabled",
                  "steps": [step({"EStop": True, "ReqSlow": False, "ReqFast": True,
                                  "FastEnable": True}, {slow: False, fast: True})]})
    return S


def _alloff_body(meta):
    outs = meta["interface"]
    lines = []
    for v in outs:
        if v["direction"] != "output":
            continue
        off = "FALSE" if v["type"] == "BOOL" else str(int(v["range"][0]) if v.get("range") else 0)
        lines.append(f"    {v['name']} := {off};")
    return "\n".join(lines)


def _alloff_program(ref_st, meta):
    ends = [m.end() for m in re.finditer(r"\bEND_VAR\b", ref_st)]
    header = ref_st[:ends[-1]] + "\n" if ends else ref_st
    return f"{header}\n{_alloff_body(meta)}\n\nEND_PROGRAM\n"


def _scen_objs(dicts):
    return [Scenario.model_validate(d) for d in dicts]


def synth_scenarios(meta, ref_st, require_discriminating=True):
    """Return the subset of candidate scenarios that the reference PASSES and (if
    require_discriminating) an all-off controller FAILS. Empty list if none."""
    cands = _candidates(meta)
    if not cands:
        return []
    try:
        ref_res = {sid: ok for sid, ok, _ in
                   check_scenarios_src(ref_st, _scen_objs(cands))}
    except Exception:  # noqa: BLE001
        return []
    kept = [c for c in cands if ref_res.get(c["id"])]
    if not kept:
        return []
    if require_discriminating:
        alloff = _alloff_program(ref_st, meta)
        try:
            off_res = {sid: ok for sid, ok, _ in
                       check_scenarios_src(alloff, _scen_objs(kept))}
        except Exception:  # noqa: BLE001
            off_res = {}
        kept = [c for c in kept if not off_res.get(c["id"], False)]
    return kept
