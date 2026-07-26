"""Phase C: LLM generation + evaluation.

Prompt an LLM with a task's natural-language spec + interface, extract the
generated IEC 61131-3 Structured Text, and score it with the same harness used
for references (compile + model-check safety properties + scenarios). This turns
the benchmark into an evaluation of how well models produce *verifiably safe*
PLC code.
"""
