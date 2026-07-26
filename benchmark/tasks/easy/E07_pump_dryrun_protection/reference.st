PROGRAM pump_ctrl
VAR_INPUT
    Demand   : BOOL;
    LowLevel : BOOL;
END_VAR
VAR_OUTPUT
    Pump : BOOL;
END_VAR

(* Dry-run protection is a hard override; otherwise follow demand. *)
IF LowLevel THEN
    Pump := FALSE;
ELSIF Demand THEN
    Pump := TRUE;
ELSE
    Pump := FALSE;
END_IF;

END_PROGRAM
