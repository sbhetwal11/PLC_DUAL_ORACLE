PROGRAM motor_interlock
VAR_INPUT
    Start : BOOL;
    Stop  : BOOL;
    EStop : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Motor : BOOL;
END_VAR

(* Priority chain: emergency stop > stop > start > hold (latch).
   When no condition matches, Motor keeps its previous value. *)
IF NOT EStop THEN
    Motor := FALSE;
ELSIF Stop THEN
    Motor := FALSE;
ELSIF Start THEN
    Motor := TRUE;
END_IF;

END_PROGRAM
