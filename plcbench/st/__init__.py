"""A focused IEC 61131-3 Structured Text subset: parser, interpreter, and
SMV translator.

Supported subset (sufficient for the benchmark; documented limits enforced by
the parser, which raises STSyntaxError on anything outside it):
 - PROGRAM ... END_PROGRAM
 - VAR_INPUT / VAR_OUTPUT / VAR / VAR CONSTANT blocks; types BOOL, INT
 - statements: assignment (:=), IF / ELSIF / ELSE / END_IF
 - expressions: NOT/AND/OR (and !,&,|), comparisons (=,<>,<,<=,>,>=),
    +,-,*, MOD, parentheses, identifiers, integer literals, TRUE/FALSE

Scan-cycle semantics: inputs are free each cycle; outputs/internal variables are
state that updates per scan via sequential, top-to-bottom assignment (a variable
keeps its value if not assigned - latching). This matches PLC execution and is
what both the interpreter and the SMV translation implement.
"""
from .parser import parse_program, STSyntaxError  # noqa: F401
