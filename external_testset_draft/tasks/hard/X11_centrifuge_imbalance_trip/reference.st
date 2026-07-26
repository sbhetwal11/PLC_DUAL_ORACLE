(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM centrifuge
VAR_INPUT
    StartCmd  : BOOL;
    Imbalance : INT;   (* scaled vibration level, 0..100 *)
    ZeroSpeed : BOOL;  (* TRUE = rotor at rest *)
    Lid       : BOOL;  (* TRUE = lid closed *)
    Reset     : BOOL;
    EStop     : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Drive     : BOOL;
    Trip      : BOOL;
    LockedOut : BOOL;
END_VAR
VAR
    Tcoast : TON;
END_VAR
VAR CONSTANT
    VIB_MAX : INT := 70;
END_VAR

(* Coast-down timer: measures continuous at-rest time once tripped.
   Called once, top level; Trip here is the previous-scan value. *)
Tcoast(IN := Trip AND ZeroSpeed, PT := T#3s);

(* Trip latch. The coast dwell (Tcoast.Q) gates only the CLEAR path, and the
   clear also requires the start command NOT be held, so the drive cannot
   restart straight through a reset - the operator must release StartCmd. *)
IF Reset AND ZeroSpeed AND Tcoast.Q AND (Imbalance < VIB_MAX) AND EStop AND NOT StartCmd THEN
    Trip := FALSE;
ELSIF (Imbalance >= VIB_MAX) AND EStop THEN
    Trip := TRUE;
END_IF;

(* Drive permissive. *)
IF NOT EStop OR NOT Lid OR Trip THEN
    Drive := FALSE;
ELSIF StartCmd THEN
    Drive := TRUE;
ELSE
    Drive := FALSE;
END_IF;

LockedOut := Trip;

END_PROGRAM
