"""Benchmark data model (pydantic v2).

A *Task* is one benchmark item: a natural-language control requirement, a typed
I/O interface, a set of formal SAFETY PROPERTIES, optional execution scenarios,
and a reference Structured Text solution. The LLM is given (nl_spec + interface)
and must produce ST code; the harness scores it by compiling and model-checking
the safety_properties.

LTL/CTL formulas are written in a tool-agnostic form over the interface variable
names (e.g. "G(!EStop -> !Motor)"). Backends translate them to nuXmv/PLCverif.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class VarDir(str, Enum):
    input = "input"
    output = "output"
    internal = "internal"


class IOVar(BaseModel):
    name: str
    type: str = Field(description="IEC 61131-3 type: BOOL, INT, REAL, TIME, ...")
    direction: VarDir
    description: str = ""
    # [min, max] for numeric types; used to bound the model-checker's state space
    range: Optional[list[float]] = None

    @field_validator("range")
    @classmethod
    def _range_pair(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError("range must be [min, max]")
        return v


class PropertyKind(str, Enum):
    safety = "safety"        # nothing bad ever happens: G(...)
    invariant = "invariant"  # a state predicate always holds
    liveness = "liveness"    # something good eventually happens: F/GF(...)


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"


class SafetyProperty(BaseModel):
    id: str
    kind: PropertyKind
    nl: str = Field(description="Plain-language statement of the property")
    ltl: Optional[str] = Field(default=None, description="LTL over interface vars")
    ctl: Optional[str] = Field(default=None, description="CTL over interface vars")
    severity: Severity = Severity.high

    @field_validator("ctl")
    @classmethod
    def _need_a_formula(cls, v, info):
        if v is None and info.data.get("ltl") is None:
            raise ValueError("property needs at least one of ltl/ctl")
        return v


class ScenarioStep(BaseModel):
    inputs: dict[str, object] = Field(default_factory=dict)
    expect: dict[str, object] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str
    description: str = ""
    steps: list[ScenarioStep] = Field(default_factory=list)


class Task(BaseModel):
    id: str
    title: str
    difficulty: Difficulty
    domain: str = Field(description="e.g. motor control, process control, safety")
    nl_spec: str = Field(description="The requirement handed to the LLM")
    interface: list[IOVar]
    safety_properties: list[SafetyProperty]
    scenarios: list[Scenario] = Field(default_factory=list)
    reference_st_file: str = "reference.st"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("safety_properties")
    @classmethod
    def _need_a_property(cls, v):
        if not v:
            raise ValueError("a task must define at least one safety property")
        return v

    def var(self, name: str) -> Optional[IOVar]:
        return next((x for x in self.interface if x.name == name), None)
