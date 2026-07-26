PROGRAM heater_ctrl
VAR_INPUT
    HeatRequest : BOOL;
    Enable      : BOOL;
    OverTemp    : BOOL;
END_VAR
VAR_OUTPUT
    Heater : BOOL;
END_VAR

(* Over-temperature is a hard safety override; otherwise follow demand when enabled. *)
IF OverTemp THEN
    Heater := FALSE;
ELSIF HeatRequest AND Enable THEN
    Heater := TRUE;
ELSE
    Heater := FALSE;
END_IF;

END_PROGRAM
