(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM ph_dosing
VAR_INPUT
    pH       : INT;   (* scaled pH x 10, 0..140 *)
    Agitator : BOOL;
    Enable   : BOOL;
    EStop    : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    AcidValve  : BOOL;
    BaseValve  : BOOL;
    OutOfRange : BOOL;
END_VAR
VAR CONSTANT
    PH_LOW      : INT := 65;
    PH_HIGH     : INT := 75;
    PH_MIN_SAFE : INT := 20;
    PH_MAX_SAFE : INT := 120;
END_VAR

(* Out-of-safe-band fault (sensor / over-range). *)
OutOfRange := (pH < PH_MIN_SAFE) OR (pH > PH_MAX_SAFE);

(* Three-region window dosing, gated by mixing / enable / health.
   A fault inhibits all dosing. *)
IF NOT EStop OR NOT Enable OR NOT Agitator OR OutOfRange THEN
    AcidValve := FALSE;
    BaseValve := FALSE;
ELSIF pH > PH_HIGH THEN
    AcidValve := TRUE;
    BaseValve := FALSE;
ELSIF pH < PH_LOW THEN
    AcidValve := FALSE;
    BaseValve := TRUE;
ELSE
    AcidValve := FALSE;
    BaseValve := FALSE;
END_IF;

END_PROGRAM
