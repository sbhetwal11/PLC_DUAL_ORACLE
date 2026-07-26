"""Build the generation prompt for a task."""
from __future__ import annotations

from ..schema import Task


def build_prompt(task: Task) -> str:
    lines = [
        "You are an expert PLC programmer. Write IEC 61131-3 Structured Text (ST) "
        "that implements the following control requirement.",
        "",
        "REQUIREMENT:",
        task.nl_spec,
        "",
        "INTERFACE (use EXACTLY these names and directions):",
    ]
    for v in task.interface:
        rng = f", range {v.range}" if v.range else ""
        lines.append(f"  - {v.name} : {v.type} [{v.direction.value}{rng}] - {v.description}")
    lines += [
        "",
        "RULES:",
        "- Output ONLY one ST program: a single PROGRAM ... END_PROGRAM block.",
        "- No prose, no markdown fences, no comments outside the program.",
        "- Declare inputs/outputs with VAR_INPUT/VAR_OUTPUT; you may add internal VAR, "
        "VAR CONSTANT, and TON timer instances as needed.",
        "- Use only: BOOL/INT types, IF/ELSIF/ELSE, CASE, assignment, TON timers "
        "(declare `Name : TON;`, call as `Name(IN := <bool>, PT := <TIME literal, "
        "e.g. T#3s>);`, read `Name.Q`), and boolean/comparison/arithmetic operators.",
        "- Timer presets are TIME literals like T#3s (treated as whole-second ticks).",
        "- The safety of the result will be checked by formal verification, so respect "
        "every stated safety condition.",
    ]
    return "\n".join(lines)
