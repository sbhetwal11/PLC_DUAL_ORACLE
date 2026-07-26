"""Extract an ST PROGRAM block from an LLM response."""
from __future__ import annotations

import re


def extract_st(text: str) -> str:
    # 1) prefer a fenced code block if present
    m = re.search(r"```[a-zA-Z0-9_+\-]*\s*\n(.*?)```", text, re.DOTALL)
    body = m.group(1) if m else text
    # 2) pull out the PROGRAM ... END_PROGRAM span
    m2 = re.search(r"(PROGRAM\b.*?\bEND_PROGRAM)", body, re.DOTALL | re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return body.strip()
