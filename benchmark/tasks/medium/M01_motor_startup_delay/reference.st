PROGRAM motor_delay
VAR_INPUT
    StartCmd : BOOL;
    EStop    : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Motor : BOOL;
END_VAR
VAR
    T1 : TON;
END_VAR

(* On-delay timer counts only while start is commanded and the system is healthy.
   T#3s = 3 scan ticks (1 tick = 1 s discrete-time abstraction). *)
T1(IN := StartCmd AND EStop, PT := T#3s);

IF NOT EStop THEN
    Motor := FALSE;
ELSIF T1.Q THEN
    Motor := TRUE;
ELSE
    Motor := FALSE;
END_IF;

END_PROGRAM
