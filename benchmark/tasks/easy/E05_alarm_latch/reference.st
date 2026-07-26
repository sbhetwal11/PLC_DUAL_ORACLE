PROGRAM alarm_ctrl
VAR_INPUT
    Trip  : BOOL;
    Reset : BOOL;
END_VAR
VAR_OUTPUT
    Alarm : BOOL;
END_VAR

(* Set-dominant latch: an active trip always sets and holds the alarm;
   Reset clears it only when the trip has cleared. *)
IF Trip THEN
    Alarm := TRUE;
ELSIF Reset THEN
    Alarm := FALSE;
END_IF;

END_PROGRAM
