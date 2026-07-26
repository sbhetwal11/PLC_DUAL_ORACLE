PROGRAM conveyor_ctrl
VAR_INPUT
    StartPB     : BOOL;
    StopPB      : BOOL;
    GuardClosed : BOOL;
    Fault       : BOOL;
END_VAR
VAR_OUTPUT
    Conveyor : BOOL;
END_VAR

(* De-energize on any stop condition; otherwise start only when permitted. *)
IF StopPB OR NOT GuardClosed OR Fault THEN
    Conveyor := FALSE;
ELSIF StartPB AND GuardClosed AND NOT Fault THEN
    Conveyor := TRUE;
END_IF;

END_PROGRAM
